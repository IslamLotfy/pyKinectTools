"""
Main file for training multi-camera pose
"""

#import os
#import time
import itertools as it
import optparse
import cPickle as pickle

import numpy as np
import cv2
import scipy.misc as sm
import scipy.ndimage as nd
import skimage
from skimage import color
from skimage.draw import line, circle
from skimage.color import rgb2gray,gray2rgb, rgb2lab
from skimage.feature import hog, local_binary_pattern, match_template, peak_local_max

from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.kernel_approximation import SkewedChi2Sampler, AdditiveChi2Sampler, RBFSampler
#from sklearn.multiclass import OneVsOneClassifier,OneVsRestClassifier
from sklearn.linear_model import SGDClassifier
from sklearn.svm import SVC
from sklearn.metrics.pairwise import chi2_kernel
from sklearn.metrics import pairwise_distances

from pyKinectTools.utils.KinectPlayer import KinectPlayer, display_help
from pyKinectTools.utils.DepthUtils import *
from pyKinectTools.utils.SkeletonUtils import display_skeletons, transform_skels, kinect_to_msr_skel, msr_to_kinect_skel
from pyKinectTools.dataset_readers.MSR_DailyActivities import MSRPlayer
from pyKinectTools.dataset_readers.EVALPlayer import EVALPlayer
from pyKinectTools.algs.GeodesicSkeleton import *
from pyKinectTools.algs.HistogramOfOpticalFlow import hog2image
from pyKinectTools.algs.BackgroundSubtraction import fillImage
from pyKinectTools.algs.PoseTracking import *

from IPython import embed
np.seterr(all='ignore')

from joblib import Parallel, delayed

"""
Felzenszwalb w/ 1 channel 133 ms per loop
Felzenszwalb w/ 3 channels 420 ms per loop
Adaptive 55ms per loop
HOG on person bounding box: 24 ms
HOG on person whole body: 101 ms for 4x4 px/cell and 70 ms for 8x8 px/cell for 24*24 px boxes
HOG per extrema 2-3 ms

It's not computationally efficient to compute hogs everywhere? What about multi-threaded? gpu?
"""

if 0:
	# Chi Squared Kernel
	svm = SVC(kernel=chi2_kernel)
	svm.fit(features['Gray_HOGs'], labels)
	svm.score(features['Gray_HOGs'], labels)

class MultiChannelClassifier:
	channel_kernels = []
	channel_names = []
	channel_means = []
	channel_data = []

	cl = None #classifier
	kernel = None

	def add_kernel(self, name, kernel, data):
		"""
		kernel : (e.g. AdditiveChi2Sampler(sample_steps=1))
		"""
		data = kernel.fit_transform(data)
		self.channel_data += [data]
		kernel_mean = data.mean()
		
		self.channel_names += [name]
		self.channel_kernels += [kernel]
		self.channel_means += [kernel_mean]		

	def fit(self, classifier, labels, kernel=None):
		"""
		classifier : (e.g. SGDClassifier(alpha=.0001, n_jobs=-1))
		kernel : (e.g. RBFSampler())
		"""
		self.cl = classifier
		data = np.sum()

		# for i in channel_kernels
		# if kernel != None:


	def predict(self, data):
		"""
		data : (e.g. {'Gray_HOGs':data, 'Color_LBPs':data}
		"""
		output = []
		data_transform = 0
		for i in len(data):
			output += [self.chi_kernels[i].transform(data[i])]


	def fit_transform(self, classifier, labels, kernel=None):
		self.fit(classifier, labels, kernel)
		self.predict()

def recenter_image(im):
	"""
	"""
	n_height, n_width = im.shape
	com = nd.center_of_mass(im)
	if any(np.isnan(com)):
		return im
	
	im_center = im[(com[0]-n_height/2):(com[0]+n_height/2)]
	offset = [(n_height-im_center.shape[0]),(n_width-im_center.shape[1])]
	
	if offset[0]%2 > 0:
		h_odd = 1
	else:
		h_odd = 0
	if offset[1]%2 > 0:
		w_odd = 1
	else:
		w_odd = 0			
	
	im[offset[0]/2:n_height-offset[0]/2-h_odd, offset[1]/2:n_width-offset[1]/2-w_odd] = im_center

	return im

def visualize_top_ims(ims, labels, count=25):
	"""
	ims : (e.g. ims_rgb, ims_gray)
	"""
	count = 25
	ims = ims_rgb
	n_classes = len(np.unique(labels))
	for j in xrange(n_classes):
		figure(j)
		i=0
		i2=0
		try:
			while i < count:
				i2 += 1#*ims.shape[0]/count/n_classes
				if labels[i2] == j:
					subplot(5,5,i);
					imshow(ims[i2])
					i += 1
		except:
			print 'Error'
			pass
	show()

def visualize_filters(filters):
	# Viz filters
	for i,im in enumerate(filters):
		ii = i*2
		subplot(3,2,ii+1)
		imshow(im*(im>0))
		subplot(3,2,ii+2)
		imshow(im*(im<0))
	show()

if 0:
	# Hard Mining
	X = features['Gray_HOGs']
	for joint_class in range(2):
		# Train on all data
		svm_head = SGDClassifier(n_iter=100, alpha=.0001)
		labels_head = labels == joint_class
		svm_head.fit(X, labels_head.astype(np.int))
		svm_head.score(X, labels_head.astype(np.int))
		filters = [hog2image(c, [height,width], orientations=5, pixels_per_cell=hog_size, cells_per_block=[3,3]) for c in svm_head.coef_]

		# Find false positives in negative data
		neg_data = X[-labels_head]
		pred = svm_head.predict(neg_data)
		# neg_data = 
		print pred.sum(), "errors in class", joint_class
		# Retrain on all of the positives and the false positives in the negative samples
		svm_head = SGDClassifier(n_iter=100, alpha=.0001)



def train(ims_rgb, ims_depth, labels):
	"""
	"""

	# --------- Setup -------- 

	# Joint options: head, shoulders, hands, feat
	joint_set = ['head', 'hands']
	n_classes = len(joint_set)
	# Image options: gray, lab
	image_set = ['gray', 'lab']
	# Feature options: Gray_HOGs, Color_LBPs, Color_Histogram
	feature_set = ['Gray_HOGs']
	features = {}	

	model_params = {}
	model_params = {'feature_set':feature_set, 'image_set':image_set, \
				'joints':joint_set, 'patch_size':patch_size}
	
	n_samples = labels.shape[0]
	height, width = ims_rgb[0].shape[:2]

	mcc = MultiChannelClassifier()
	# mcc.add_classifier(SGDClassifier(n_iter=100, alpha=.0001, n_jobs=-1))

	#  --------- Conversions --------- 

	print 'Converting images'
	if 'gray' in image_set:
		ims_gray = (np.array([rgb2gray(ims_rgb[i]) for i in range(n_samples)])*255).astype(np.uint8)
	if 'lab' in image_set:
		ims_lab = np.array([rgb2lab(ims_rgb[i]) for i in range(n_samples)])

	print 'Relabeling classes'
	joints = {'head':[0], 'shoulders':[2,5], 'hands':[4,7], 'feat':[10,13]}
	classes = [joints[j] for j in joint_set]
	
	# Group into classes
	labels_orig = labels.copy()
	for c in xrange(n_samples):
		this_class = n_classes
		for i in xrange(n_classes):
			if labels[c] in classes[i]:
				this_class = i
				break
		labels[c] = this_class
		# ims_c[c] = recenter_image(ims_c[c])

	# visualize_top_ims(ims_rgb, labels)

	# --------- Calculate features --------- 
	print ""
	print '--Starting feature calculations--'

	if 'Gray_HOGs' in feature_set:
		print 'Calculating Grayscale HOGs'
		model_params['hog_size'] = (8,8)
		model_params['hog_cells']= (1,1)
		model_params['hog_orientations'] = 5
		hogs_c = Parallel(n_jobs=-1)(delayed(hog)(im, 5, (8,8), (1,1), False, False) for im in ims_gray)
		hogs_c = np.array(hogs_c)
		# Ensure no negative values
		hogs_c[hogs_c<0] = 0
		features['Gray_HOGs'] = hogs_c
		mcc.add_kernel('Gray_HOGs', AdditiveChi2Sampler(1), hogs_c)

	if 'Depth_HOGs' in feature_set:
		print 'Calculating Depth-based HOGs'
		model_params['hog_size'] = (8,8)
		model_params['hog_cells']= (3,3)
		model_params['hog_orientations'] = 9
		hogs_c = Parallel(n_jobs=-1)(delayed(hog)(im, 5, (8,8), (3,3), False, False) for im in ims_depth)
		hogs_c = np.array(hogs_c)
		features['Depth_HOGs'] = hogs_c		

	if 'Color_LBPs' in feature_set:
		print 'Calculating Color LBPs'
		model_params['lbp_px'] = 16
		model_params['lbp_radius'] = 2
		lbps_tmp = np.array(Parallel(n_jobs=-1)(delayed(local_binary_pattern)(im, P=16, R=2, method='uniform') for im in ims_gray ))
		lbps_c = np.array(Parallel(n_jobs=-1)(delayed(np.histogram)(lbp, normed=True, bins = 18, range=(0,18)) for lbp in lbps_tmp ))
		lbps_c = np.array([x[0] for x in lbps_c])
		# Get rid of background and ensure no negative values
		lbps_c[:,lbps_c.argmax(1)]=0
		lbps_c = (lbps_c.T/lbps_c.sum(1)).T
		lbps_c = np.nan_to_num(lbps_c)
		features['Color_LBPs'] = lbps_c

	if 'Depth_LBPs' in feature_set:
		print 'Calculating Depth LBPs'
		lbps_tmp = np.array(Parallel(n_jobs=-1)(delayed(local_binary_pattern)(im, P=16, R=2, method='uniform') for im in ims_depth ))
		lbps_z = np.array(Parallel(n_jobs=-1)(delayed(np.histogram)(lbp, normed=True, bins = 18, range=(0,18)) for lbp in lbps_tmp ))
		lbps_z = np.array([x[0] for x in lbps_z])
		# Get rid of background and ensure no negative values
		lbps_z[:,lbps_z.argmax(1)]=0
		lbps_z = (lbps_z.T/lbps_z.sum(1)).T
		lbps_z = np.nan_to_num(lbps_z)
		features['Depth_LBPs'] = lbps_z

	if 'Color_Histograms' in feature_set:
		print 'Calculating Color Histograms'
		color_hists = np.array([np.histogram(ims_lab[i,:,:,0], 10, [1,255])[0] for i in xrange(n_samples)])
		features['Color_Histograms'] = color_hists

	if 'Curvature' in feature_set:
		print 'Calculating Geometric Curvature'
		# TODO
		# features['Geometric_Curvature'] = 

	if 'Hand_Template' in feature_set:
		print 'Calculating Hand Template features'
		# TODO
		# features['Hand_Template'] = 

	if 'Face_Template' in feature_set:
		print 'Calculating Face Template features'
		# TODO
		# features['Face_Template'] = 


	# Transfrom  pca/chi/rbf
	# pca = PCA(13)
	# rbf = RBFSampler()
	data = features['Gray_HOGs']
	labels = np.array([labels[i] for i,x in enumerate(data) if sum(x)!= 0])
	data = np.vstack([x/x.sum() for x in features['Gray_HOGs'] if sum(x)!= 0])
	# data = data / np.repeat(data.sum(-1)[:,None], data.shape[-1], -1)
	# data = np.nan_to_num(data)
	chi2 = AdditiveChi2Sampler(1)
	model_params['Chi2'] = chi2
	training_data = chi2.fit_transform(data)
	training_labels = labels

	# --------- Classification --------- 
	print ""
	print 'Starting classification training'
	svm = SGDClassifier(n_iter=100, alpha=.0001, class_weight="auto", l1_ratio=0, fit_intercept=True, n_jobs=-1)
	svm.fit(training_data, training_labels)
	print "Done fitting both SVM. Self score: {0:.2f}%".format(svm.score(training_data, training_labels)*100)
	model_params['SVM'] = svm

	filters = svm.coef_
	# filters = [hog2image(c, [height,width], orientations=5, pixels_per_cell=model_params['hog_size'], cells_per_block=[3,3]) for c in svm.coef_]
	model_params['filters'] = filters
	# filters = [f*(f>0) for f in filters]

	# rf = RandomForestClassifier(n_estimators=50)
	# rf.fit(training_both_kernel, labels)
	# print "Done fitting forest. Self score: {0:.2f}%".format(rf.score(training_both_kernel, labels)*100)
	# model_params['rf'] = rf

	# Grid search for paramater estimation
	if 0:
		from sklearn.grid_search import GridSearchCV
		from sklearn.cross_validation import cross_val_score
		params = {'alpha': [.0001],
				'l1_ratio':[0.,.25,.5,.75,1.]}
		grid_search = GridSearchCV(svm_both, param_grid=params, cv=2, verbose=3)	
		grid_search.fit(training_both_kernel, labels)

	# --------- Save Model Information --------- 
	model_params['Description'] = ''
	with open('model_params.dat', 'w') as f:
		pickle.dump(model_params, f)
	print 'Parameters saved. Process complete'





# -------------------------MAIN------------------------------------------

def main(visualize=False, learn=False, patch_size=32, n_frames=2500):

	if 1:
		get_color = True
		cam = KinectPlayer(base_dir='./', device=1, bg_subtraction=True, get_depth=True, get_color=True, get_skeleton=True, fill_images=False)	
		cam.bgSubtraction.backgroundModel = sm.imread('/Users/colin/Data/CIRL_28Feb2013/depth/59/13/47/device_1/depth_59_13_47_4_13_35507.png').clip(0, 3500)
		# cam = KinectPlayer(base_dir='./', device=2, bg_subtraction=True, get_depth=True, get_color=True, get_skeleton=True, fill_images=False)	
		# cam = MSRPlayer(base_dir='/Users/colin/Data/MSR_DailyActivities/Data/', actions=[1], subjects=[1,2,3,4,5], bg_subtraction=True, get_depth=True, get_color=True, get_skeleton=True, fill_images=False)
	elif 1:
		get_color = False
		cam = EVALPlayer(base_dir='/Users/colin/Data/EVAL/', bg_subtraction=True, get_depth=True, get_skeleton=True, fill_images=False)
	height, width = cam.depthIm.shape

	if learn:
		n_joints = 14
		rez = [480,640]
		ims_depth = np.empty([n_frames*n_joints, patch_size, patch_size], dtype=np.uint16)
		ims_rgb = np.empty([n_frames*n_joints, patch_size, patch_size, 3], dtype=np.uint8)		
		labels = np.empty(n_frames*n_joints, dtype=np.int)
	else:
		model_params = pickle.load(open('model_params.dat', 'r'))
		patch_size = model_params['patch_size']
		svm = model_params['SVM']
		filters = model_params['filters'] 
		filters *= filters > 0
		n_filters = len(filters)

		true_pos = {'hands':0, 'head':0}
		false_pos = {'hands':0, 'head':0}

	skel_names = np.array(['head', 'neck', 'torso', 'l_shoulder', 'l_elbow', 'l_hand', \
				'r_shoulder', 'r_elbow', 'r_hand', 'l_hip', 'l_knee', 'l_foot',\
				'r_hip', 'r_knee', 'r_foot'])
	skel_init = np.array([
		[-650,0,0], # head
		[-425,0,0], # neck
		[-150,0,0],# torso
		[-425,-150,0],# l shoulder
		[-150,-250,0],# l elbow
		[50,-350,0],# l hand
		[-425,150,0],# r shoulder
		[-150,250,0],# r elbow
		[50,350,0],# r hand
		[000,-110,0],# l hip
		[450,-110,0],# l knee
		[600,-110,0],# l foot
		[000,110,0],# r hip
		[450,110,0],# r knee
		[600,110,0],# r foot
		])
	joint_size = np.array([
		50, # head
		50, # neck
		100,# torso
		50,# l shoulder
		50,# l elbow
		50,# l hand
		50,# r shoulder
		50,# r elbow
		50,# r hand
		50,# l hip
		50,# l knee
		50,# l foot
		50,# r hip
		50,# r knee
		50,# r foot
		])	
	constraint_links = np.array([
		[0,1],[1,2],[3,6],[0,3],[0,6],#Head to neck, neck to torso, shoulders, head to shoulders
		[1,3],[3,4],[4,5], # Left arm
		[3,9],[6,12], # shoudlers to hips
		[1,6],[6,7],[7,8], # Right arm
		[2,9],[9,10],[10,11], #Left foot
		[2,12],[12,13],[13,14], #Right foot
		[9,12] #Bridge hips
		])
	constraint_values = []
	for c in constraint_links:
		constraint_values += [np.linalg.norm(skel_init[c[0]]-skel_init[c[1]], 2)]
	constraint_values = np.array(constraint_values)

	skel_current = skel_init.copy()
	skel_previous = skel_current.copy()

	
	face_detector = FaceDetector()

	frame_count = 0
	if get_color and height==240:
		cam.next(220)
	while cam.next(1) and frame_count < n_frames:
		# Get rid of bad skeletons
		if type(cam.users)==dict:
			cam_skels = [np.array(cam.users[s]['jointPositions'].values()) for s in cam.users]
		else:
			cam_skels = [np.array(s) for s in cam.users]
		cam_skels = [s for s in cam_skels if np.all(s[0] != -1)]

		# Check for skeletons
		# if len(cam_skels) == 0:
			# continue	

		# Apply mask to image
		mask = cam.get_person() > 0
		if mask is False:
			continue

		# Anonomize
		# c_masked = cam.colorIm*mask[:,:,None]
		# d_masked = cam.depthIm*mask
		# c_masked_neg = cam.colorIm*(-mask[:,:,None])
		
		im_depth =  cam.depthIm
		if get_color:
			im_color = cam.colorIm
			im_color *= mask[:,:,None]
			im_color = np.ascontiguousarray(im_color)		
			im_color = im_color[:,:,[2,1,0]]
		if len(cam_skels) > 0:
			skel_msr_xyz = cam_skels[0]
			skel_msr_im = skel2depth(cam_skels[0], cam.depthIm.shape)


		if learn:
			# Use offsets surounding joints
			for i,j_pos in enumerate(skel_msr_im):
				x = j_pos[1]
				y = j_pos[0]
				if x-patch_size/2 >= 0 and x+patch_size/2 < height and y-patch_size/2 >= 0 and y+patch_size/2 < width:
					ims_rgb[frame_count*n_joints+i] = im_color[x-patch_size/2:x+patch_size/2, y-patch_size/2:y+patch_size/2]
					ims_depth[frame_count*n_joints+i] = im_depth[x-patch_size/2:x+patch_size/2, y-patch_size/2:y+patch_size/2]
					labels[frame_count*n_joints+i] = i
				else:
					labels[frame_count*n_joints+i] = -1
		else:
			box = nd.find_objects(mask)[0]
			box = np.pad(im_depth[box], 2, 'edge')
			# box = (box[0].start - np.clip(box[0].start-10, 0, 999)
			# box = ((box[0].start-10, box[0].stop+10), (box[1].start-10, box[1].stop+10))
			# Ensure the size is a multiple of HOG size
			# box = (slice(box[0].start, ((box[0].stop - box[0].start) / model_params['hog_size'][0])*model_params['hog_size'][0] + box[0].start),
					# slice(box[1].start, ((box[1].stop - box[1].start) / model_params['hog_size'][1])*model_params['hog_size'][1] + box[1].start))

			if get_color:
				# Face detection
				face_detector.run(im_color[box])

			# Skin detection
			if 1:
				if 'gray' in model_params['image_set']:
					im_gray = (rgb2gray(cam.colorIm)*255).astype(np.uint8)
					im_gray *= mask
				if 'lab' in model_params['image_set']:
					# im_lab = (rgb2lab(cam.colorIm)*255).astype(np.uint8)
					# im_lab = rgb2lab(cam.colorIm[box][:,:,[2,1,0]].astype(np.uint16))[:,:,1]
					im_skin = rgb2lab(cam.colorIm[box].astype(np.int16))[:,:,1]
					# im_skin = skimage.exposure.equalize_hist(im_skin)
					# im_skin = skimage.exposure.rescale_intensity(im_skin, out_range=[0,1])
					im_skin *= im_skin > face_detector.min_threshold
					im_skin *= im_skin < face_detector.max_threshold
					# im_skin *= face_detector>.068
				
					hand_template = sm.imread('/Users/colin/Desktop/fist.png')[:,:,2]
					hand_template = (255 - hand_template)/255.
					if height == 240:
						hand_template = cv2.resize(hand_template, (10,10))
					else:
						hand_template = cv2.resize(hand_template, (20,20))
					skin_match_c = nd.correlate(im_skin, hand_template)

					# hand_template = (1. - hand_template)
					# hand_template = cv2.resize(hand_template, (20,20))
					# skin_match_d = nd.correlate(im_depth[box]/256., 0.5-hand_template)

					# Display Predictions - Color Based matching
					optima = peak_local_max(skin_match_c, min_distance=20, num_peaks=3, exclude_border=False)
					if len(optima) > 0:
						optima_values = skin_match_c[optima[:,0], optima[:,1]]
						optima_thresh = np.max(optima_values) / 2
						optima = optima.tolist()

						for i,o in enumerate(optima):
							if optima_values[i] < optima_thresh:
								optima.pop(i)
								break
							joint = np.array(o) + [box[0].start, box[1].start]
							circ = np.array(circle(joint[0],joint[1], 5)).T
							circ = circ.clip([0,0], [height-1, width-1])
							cam.colorIm[circ[:,0], circ[:,1]] = (0,120 - 30*i,0)#(255*(i==0),255*(i==1),255*(i==2))
					markers = optima

					if 0:
						pass
						# Depth-based matching
						# optima = peak_local_max(skin_match_d, min_distance=20, num_peaks=3, exclude_border=False)
						# for i,o in enumerate(optima):
						# 	joint = o + [box[0].start, box[1].start]
						# 	circ = np.array(circle(joint[0],joint[1], 10))
						# 	circ = circ.clip([0,0,0], [height-1, width-1, 999])
						# 	cam.colorIm[circ[0], circ[1]] = (0,0,255-40*i)#(255*(i==0),255*(i==1),255*(i==2))

						# im_pos = depthIm2PosIm(cam.depthIm).astype(np.int16)
						# im_pos = im_pos[box]*mask[box][:,:,None]

						# cost_map = im_depth[box]
						# extrema = geodesic_extrema_MPI(im_pos, iterations=5, visualize=False)
						# if len(extrema) > 0:						
						# 	for i,o in enumerate(extrema):
						# 		joint = np.array(o) + [box[0].start, box[1].start]
						# 		circ = np.array(circle(joint[0],joint[1], 10)).T
						# 		circ = circ.clip([0,0], [height-1, width-1])
						# 		cam.colorIm[circ[:,0], circ[:,1]] = (0,0,120-30*i)#(255*(i==0),255*(i==1),255*(i==2))
						# markers = optima					
						# trails = []
						# if len(markers) > 1:
						# 	for i,m in enumerate(markers):
						# 		trails_i = connect_extrema(im_pos, markers[i], markers[[x for x in range(len(markers)) if x != i]], visualize=False)
						# 		trails += trails_i
						# for t in trails:
						# 	try:
						# 		cost_map[t[:,0], t[:,1]] = 0
						# 		cam.colorIm[t[:,0]+box[0].start, t[:,1]+box[1].start] = (0,0,255)
						# 	except:
						# 		print 'Error highlighting trail'

						# cv2.imshow('SkinMap, SkinDetect, DepthDetect', 
						# 			np.hstack([ im_skin			/float(im_skin.max()),
						# 						skin_match_c	/float(skin_match_c.max())]
						# 						))




				# SVM
				if 0:
					# b_height,b_width = im_gray[box].shape
					# if im_gray[box].shape[0] < filters[0].shape[0] or im_gray[box].shape[1] < filters[0].shape[1]:
						# continue
					model_params['hog_orientations'] = 5
					# hogs_array_c, hogs_im_c = hog(im_gray[box], orientations=model_params['hog_orientations'], pixels_per_cell=model_params['hog_size'], cells_per_block=model_params['hog_cells'], visualise=True, normalise=False)
					# hogs_array_c, hogs_im_c = hog(im_gray[box], orientations=5, pixels_per_cell=(8,8), cells_per_block=(1,1), visualise=True, normalise=False)
					hogs_array_c = hog(im_gray[box], orientations=5, pixels_per_cell=(8,8), cells_per_block=(1,1), visualise=False, normalise=False)
					# hogs_array_c, hogs_im_c = hog(im_gray[box], orientations=model_params['hog_orientations'], pixels_per_cell=model_params['hog_size'], cells_per_block=(3,3), visualise=True, normalise=False)

					chi2 = model_params['Chi2']
					h_height = im_gray[box].shape[0]/model_params['hog_size'][0]#patch_size
					h_width = im_gray[box].shape[1]/model_params['hog_size'][1]#patch_size
					hog_dim = 5# * ((patch_size/model_params['hog_size'][0])*(patch_size/model_params['hog_size'][1]))#float(h_height) / h_width
					hog_patches = hogs_array_c.reshape([h_height, h_width, hog_dim])
					hog_patches[hog_patches<0]=0
					hog_out = np.zeros([h_height, h_width])-1
					for i in xrange(0, h_height):
						for j in xrange(0, h_width):
							patch = hog_patches[i:i+4, j:j+4].flatten()
							if patch.max() != 0 and patch.shape[0]==hog_dim*16:
								patch_c = chi2.transform(patch / patch.max())
								hog_out[i,j] = svm.predict(patch)[0]
								# print svm.predict(patch)[0]


					# cv2.imshow("H", hog_out)
					# cv2.waitKey(10)
					output = hog_out
					predict_class = hog_out
					# hog_patches = chi2.transform(hog_patches)
					# predict_class = svm.predict(hog_patches)
					# matshow(predict.reshape([h_height,h_width]))

					# hog_layers = np.empty([hogs_im_c.shape[0], hogs_im_c.shape[1], n_filters])
					# for i,f in enumerate(filters):
						# hog_layers[:,:,i] = match_template(hogs_im_c, f, pad_input=True)

					# predict
					# mask_tmp = np.maximum((hog_layers.max(-1) == 0), -mask[box])
					# predict_class = hog_layers[0::8,0::8].argmax(-1)*(-mask_tmp[::8,::8]) + ((-mask_tmp[::8,::8])*1)
					# predict_prob = hog_layers[0::8,0::8].max(-1)*(-mask_tmp[::8,::8]) + ((-mask_tmp[::8,::8])*1)

					# output = np.zeros([predict_class.shape[0], predict_class.shape[1], n_filters], dtype=np.float)
					# for i in range(n_filters):
					# 	output[predict_class==i+1,i] = predict_class[predict_class==i+1]+predict_prob[predict_class==i+1]
					# 	if 0 and i != 2:
					# 		for ii,jj in it.product(range(8),range(8)):
					# 			try:
					# 				cam.colorIm[box][ii::8,jj::8][predict_class==i+1] = (255*(i==0),255*(i==1),255*(i==2))
					# 			except:
					# 				pass

					# Display Predictions
					# n_peaks = [1,2,2]
					# for i in range(n_filters-1):
					# 	optima = peak_local_max(predict_prob*(predict_class==i+1), min_distance=2, num_peaks=n_peaks[i], exclude_border=False)
					# 	for o in optima:
					# 		joint = o*8 + [box[0].start, box[1].start]
					# 		circle = circle(joint[0],joint[1], 15)
					# 		circle = np.array([np.minimum(circle[0], height-1),
					# 							np.minimum(circle[1], width-1)])
					# 		circle = np.array([np.maximum(circle[0], 0),
					# 							np.maximum(circle[1], 0)])

					# 		cam.colorIm[circle[0], circle[1]] = (255*(i==0),255*(i==1),255*(i==2))

					# if 0:
					# 	for i in range(n_filters-1):
					# 		figure(i+1)
					# 		imshow(predict_prob*(predict_class==i+1))
					# 	show()

					# tmp = gray2rgb(sm.imresize(predict_class, np.array(predict_class.shape)*10, 'nearest'))
					# tmp[:,:,2] = 255 - tmp[:,:,2]
					tmp = sm.imresize(output, np.array(predict_class.shape)*10, 'nearest')
					# cv2.imshow("O", tmp/float(tmp.max()))
					# cv2.waitKey(10)

				# # Random Forest
				# if 0:
				# 	h_count = hogs_array_c.shape[0] / 9
				# 	hog_height, hog_width = [b_height/8, b_width/8]
				# 	square_size = patch_size/2*2/8
				# 	hogs_square = hogs_array_c.reshape(hog_height, hog_width, 9)
				# 	predict_class = np.zeros([hog_height, hog_width])
				# 	predict_prob = np.zeros([hog_height, hog_width])
				# 	output = predict_class
				# 	for i in range(0,hog_height):
				# 		for j in range(0,hog_width):
				# 			if i-square_size/2 >= 0 and i+square_size/2 < hog_height and j-square_size/2 >= 0 and j+square_size/2 < hog_width:
				# 				predict_class[i,j] = rf.predict(hogs_square[i-square_size/2:i+square_size/2,j-square_size/2:j+square_size/2].flatten())[0]
				# 				predict_prob[i,j] = rf.predict_proba(hogs_square[i-square_size/2:i+square_size/2,j-square_size/2:j+square_size/2].flatten()).max()


			# Calculate HOGs at geodesic extrema. The predict
			if 0:
				n_px = 16
				n_radius = 2

				extrema = geodesic_extrema_MPI(cam.depthIm*mask, iterations=10)
				extrema = np.array([e for e in extrema if patch_size/2<e[0]<height-patch_size/2 and patch_size/2<e[1]<width-patch_size/2])
				# joint_names = ['head', 'torso', 'l_shoulder', 'l_elbow', 'l_hand',\
				# 				'r_shoulder', 'r_elbow', 'r_hand',\
				# 				'l_hip', 'l_knee', 'l_foot', \
				# 				'r_hip', 'r_knee', 'r_foot']
				joint_names = ['head', 'l_hand', 'l_foot', 'other']						
				
				# Color
				if 1:
					hogs_c_pca = [hog(im_gray[e[0]-patch_size/2:e[0]+patch_size/2, e[1]-patch_size/2:e[1]+patch_size/2], 9, (8,8), (3,3), False, True) for e in extrema]					

					lbp_tmp = [local_binary_pattern(im_gray[e[0]-patch_size/2:e[0]+patch_size/2, e[1]-patch_size/2:e[1]+patch_size/2], P=n_px, R=n_radius, method='uniform') for e in extrema]
					lbp_hists_c = np.array([np.histogram(im, normed=True, bins = n_px+2, range=(0,n_px+2))[0] for im in lbp_tmp])
					lbp_hists_c[lbp_hists_c.argmax(0)] = 0
					lbp_hists_c = lbp_hists_c.T / lbp_hists_c.max(1)
					lbp_hists_c = np.nan_to_num(lbp_hists_c)
					# names = [joint_names[i] for i in hogs_c_pred]
				# Both
				if 1:
					# data_both_pca = np.array([pca_both.transform(data_both[i]) for i in range(len(data_both))]).reshape([len(extrema), -1])
					data_both_pca = np.hstack([np.array(hogs_c), lbp_hists_c.T, lbp_hists_z.T])
					data_both_pca[data_both_pca<0] = 0
					hogs_both_pred = np.hstack([svm.predict(h) for h in data_both_pca]).astype(np.int)
					names = [joint_names[i] for i in hogs_both_pred]
					skel_predict = hogs_both_pred.astype(np.int)				

				# print names
				im_c = cam.colorIm
				d = patch_size/2
				for i in range(len(extrema)):
					color = 0
					if names[i] == 'head':
						color = [255,0,0]
					elif names[i] in ('l_hand', 'r_hand'):
						color = [0,255,0]
					# elif names[i] == 'l_shoulder' or names[i] == 'r_shoulder':
						# color = [0,0,255]
					# elif names[i] == 'l_foot' or names[i] == 'r_foot':
						# color = [0,255,255]							
					# else:
						# color = [0,0,0]

					if color != 0:
						im_c[extrema[i][0]-d:extrema[i][0]+d, extrema[i][1]-d:extrema[i][1]+d] = color
					else:
						im_c[extrema[i][0]-d/2:extrema[i][0]+d/2, extrema[i][1]-d/2:extrema[i][1]+d/2] = 0
					# im_c[extrema[i][0]-d:extrema[i][0]+d, extrema[i][1]-d:extrema[i][1]+d] = lbp_tmp[i][:,:,None] * (255/18.)
						# cv2.putText(im_c, names[i], (extrema[i][1], extrema[i][0]), 0, .4, (255,0,0))
				# cv2.imshow("Label_C", im_c*mask[:,:,None])
				# cv2.waitKey(10)

				# Accuracy
				print skel_predict
				extrema_truth = np.empty(len(extrema), dtype=np.int)
				for i in range(len(extrema)):
					ex = extrema[i]
					dist = np.sqrt(np.sum((ex - skel_msr_im[:,[1,0]])**2,-1))
					extrema_truth[i] = np.argmin(dist)

					# print skel_predict[i], extrema_truth[i]
					if skel_predict[i] == 1:
						# if extrema_truth[i] == 4 or extrema_truth[i] == 7:
						if extrema_truth[i] in (11, 7):
							true_pos['hands'] += .5
						else:
							false_pos['hands'] += .5
					elif skel_predict[i] == 0:
						if extrema_truth[i] == 3:
							true_pos['head'] += 1
							print 'h correct'
						else:
							false_pos['head'] += 1
				print "Hands", true_pos['hands'] / float(frame_count)#float(false_pos['hands'])
				print "Head", true_pos['head'] / float(frame_count)##float(false_pos['head'])


			# ---------------- Ganapathi Tracking Algorithm ----------------
			# ---- Preprocessing ----
			# Todo: Sample points			
			if get_color:
				im_pos = rgbIm2PosIm(cam.depthIm*mask)[box] * mask[box][:,:,None]
			else:
				im_pos = cam.posIm[box]
			cam.depthIm[cam.depthIm==3500] = 0
			im_pos_mean = np.array([
								im_pos[:,:,0][im_pos[:,:,2]!=0].mean(),
								im_pos[:,:,1][im_pos[:,:,2]!=0].mean(),
								im_pos[:,:,2][im_pos[:,:,2]!=0].mean()
								], dtype=np.int16)

			# Zero-center
			if skel_current[0,2] == 0:
				skel_current += im_pos_mean
				skel_previous += im_pos_mean

			# Features
			extrema = geodesic_extrema_MPI(im_pos, iterations=10, visualize=False)
			if len(extrema) > 0:				
				for i,o in enumerate(extrema):
					joint = np.array(o) + [box[0].start, box[1].start]
					circ = np.array(circle(joint[0],joint[1], 5)).T
					circ = circ.clip([0,0], [height-1, width-1])
					cam.colorIm[circ[:,0], circ[:,1]] = (0,0,200-10*i)#(255*(i==0),255*(i==1),255*(i==2))

			# Z-surface
			surface_map = nd.distance_transform_edt(-mask[box], return_distances=False, return_indices=True)

			if 1:
				mask_interval = 1
				feature_radius = 10
			else:
				mask_interval = 3
				feature_radius = 2

			box = (slice(box[0].start, box[0].stop, mask_interval),slice(box[1].start, box[1].stop, mask_interval))

			im_pos_full = im_pos.copy()
			im_pos = im_pos[::mask_interval,::mask_interval]
			box_height, box_width,_ = im_pos.shape
			skel_img_box = None

			# ---- (Step 1A) Find feature coordespondences ----
			# This function does not need to be computed at every iteration
			# Set of joints used for each set of features:
			# Face detector, skin, extrema

			features_joints = [[0], [0,5,8], range(len(skel_current))]
			# features_joints = [[0], [0,5,8], [0,3,5,6,8,11,14]]
			feature_width = feature_radius*2+1
			feature_tmp = np.exp(- ((feature_radius - np.mgrid[:feature_width,:feature_width][0])**2 + (feature_radius - np.mgrid[:feature_width,:feature_width][1])**2 ) / (2.*feature_radius**2))
			feature_tmp /= np.sum(feature_tmp)
			all_features = [face_detector.face_position, optima, extrema]
			total_feature_count = np.sum([len(f) for f in all_features])

			px_feature = np.zeros([im_pos.shape[0], im_pos.shape[1], len(skel_current)])			
			for i,features in enumerate(all_features):
				for j,o_ in enumerate(features):
					o = np.array(o_)/mask_interval
					pt_xyz = im_pos[o[0], o[1]]
					o = np.clip(o, [feature_radius,feature_radius], [im_pos.shape[0]-feature_radius-1, im_pos.shape[1]-feature_radius-1])
					joint_ind = np.argmin(np.sum((skel_current[features_joints[i]] - pt_xyz)**2, 1))
					px_feature[o[0]-feature_radius:o[0]+feature_radius+1,o[1]-feature_radius:o[1]+feature_radius+1,features_joints[i][joint_ind]] += feature_tmp# * ((total_feature_count-len(features))/float(total_feature_count))

			# Find feature max labels
			px_label = np.argmax(px_feature, -1)
			px_label_flat = px_label[mask[box]].flatten()
			px_label_prob = np.max(px_feature, -1)[mask[box]].flatten()
			px_diff = skel_current[px_label_flat] - im_pos[mask[box]]

			# Calc the feature change in position for each joint
			feature_diff = np.zeros([len(skel_current), 3])
			feature_prob = np.zeros(len(skel_current))
			for i,_ in enumerate(skel_current):
				labels = px_label_flat==i
				if sum(labels) > 0:
					feature_prob[i] = 1
					px_label_prob[labels] /= np.sum(px_label_prob[labels])
					feature_diff[i] = np.sum(px_label_prob[labels][:,None]*px_diff[labels], 0)
				else:
					feature_prob[i] = 0
			feature_diff = np.nan_to_num(feature_diff)

			# Loop through the rest of the constraints
			for _ in range(20):
				# ---- (Step 1B) Find depth coordespondences ----
				px_corr = np.zeros([im_pos.shape[0], im_pos.shape[1], len(skel_current)])
				
				## Calc euclidian probabilities
				if skel_img_box is None:
					skel_img_box = world2rgb(skel_current, cam.depthIm.shape) - [box[0].start, box[1].start, 0]
					skel_img_box = skel_img_box.clip([0,0,0], [im_pos.shape[0]-1, im_pos.shape[1]-1, 9999])
				for i,s in enumerate(skel_img_box):
					px_corr[:,:,i] = np.exp(-np.sqrt(np.sum((im_pos - im_pos[s[0], s[1]])**2, -1)) / joint_size[i])
				# for i,_ in enumerate(skel_current):
					# px_corr = px_corr / px_corr.sum(-1)[:,:,None]
				px_label = np.argmax(px_corr, -1)
				
				# for i,s in enumerate(skel_current):
					# px_corr[:,:,i] = np.sum((im_pos - s)**2, -1) / joint_size[i]**2
				# px_label = np.argmin(px_corr, -1)

				px_label_flat = px_label[mask[box]].flatten()
				px_label_prob = np.max(px_corr, -1)[mask[box]].flatten()
				px_diff = skel_current[px_label_flat]-im_pos[mask[box]]
				# If within joint size, then correspondence should be zero
				px_diff[np.sqrt(np.sum(px_diff**2, 1)) < joint_size[px_label_flat]] = 0

				# Calc the correspondance change in position for each joint
				corr_diff = np.empty([len(skel_current), 3])
				for i,_ in enumerate(skel_current):
					labels = px_label_flat==i
					px_label_prob[labels] /= np.sum(px_label_prob[labels])
					corr_diff[i] = np.sum(px_label_prob[labels][:,None]*px_diff[labels], 0)
					# corr_diff[i] = np.sum(np.maximum(px_diff[labels]-joint_size[i]/2,0), 0)
				corr_diff = np.nan_to_num(corr_diff)

				# ---- (Step 2) Find occlusions ----
				# Determine if joints are visible
				# correspondances_prob = np.exp(-np.sqrt(np.sum(corr_diff**2,-1))/100.)
				# Determine if joints are visible
				visible_joints = np.exp(-np.sqrt(corr_diff[:,2]**2)/100) > .5


				# ---- (Step 3) Update pose state, x ----
				gamma = .0
				lambda_d = .5
				lambda_c = .5
				skel_prev_difference = (skel_current - skel_previous)
				skel_current = skel_previous \
								+ gamma*skel_prev_difference \
								- lambda_d*corr_diff\
								- lambda_c*feature_diff

				skel_img_box = world2rgb(skel_current, cam.depthIm.shape) - [box[0].start, box[1].start, 0]
				skel_img_box = skel_img_box.clip([0,0,0], [im_pos.shape[0]-1, im_pos.shape[1]-1, 9999])

				# ---- (Step 3) Add constraints ----
				order = np.arange(len(constraint_links))
				for _ in range(1):
					# A: Link lengths
					skel_current = link_length_constraints(skel_current, constraint_links[order], constraint_values[order], alpha=.3)
					# B: Geometry
					skel_current = geometry_constraints(skel_current, joint_size, alpha=0.8)

				# skel_img_box = (world2rgb(skel_current, cam.depthIm.shape) - [box[0].start, box[1].start, 0])/mask_interval
				# skel_img_box = skel_img_box.clip([0,0,0], [im_pos.shape[0]-1, im_pos.shape[1]-1, 9999])
				skel_img_box = (world2rgb(skel_current, cam.depthIm.shape) - [box[0].start, box[1].start, 0])				
				skel_img_box = skel_img_box.clip([0,0,0], [cam.depthIm.shape[0]-1, cam.depthIm.shape[1]-1, 9999])
				# C: Ray-cast constraints
				skel_current, skel_img_box = ray_cast_constraints(skel_current, skel_img_box, im_pos_full, surface_map, joint_size)

			# # Map back from mask to image
			skel_img = skel_img_box + [box[0].start, box[1].start, 0]
			# embed()
			# ----------------------------------------------------------------

			# Compute accuracy wrt standard Kinect data
			# skel_im_error = skel_msr_im[:,[1,0]] - skel_img[[0,2,3,4,5,6,7,8,9,10,11,12,13,14],:2]
			try:
				skel_msr_im_box = np.array([skel_msr_im[:,1]-box[0].start,skel_msr_im[:,0]-box[1].start]).T.clip([0,0],[box_height-1, box_width-1])
				skel_xyz_error = im_pos[skel_msr_im_box[:,0],skel_msr_im_box[:,1]] - skel_current[[0,2,3,4,5,6,7,8,9,10,11,12,13,14],:]
				skel_l2 = np.sqrt(np.sum(skel_xyz_error**2, 1))
			except:
				embed()
			print skel_l2
			skel_correct = np.nonzero(skel_l2 < 150)[0]
			print "{0:0.2f}% joints correct".format(len(skel_correct)/15.*100)
			# skel_error_x = skel_msr_xyz[::-1,1] - skel_current[[0,2,3,4,5,6,7,8,9,10,11,12,13,14],0]
			# skel_error_y = skel_msr_xyz[:,0] - skel_current[[0,2,3,4,5,6,7,8,9,10,11,12,13,14],1]
			# skel_error_z = skel_msr_xyz[:,2] - skel_current[[0,2,3,4,5,6,7,8,9,10,11,12,13,14],2]
			# skel_l2 = np.sqrt(np.sum(skel_error, 0))

			# print world2rgb(np.array([im_pos_mean]), (240,320))
			# mp = world2rgb(np.array([im_pos_mean]), (240,320))[0]
			# c = circle(mp[0],mp[1], 10)
			# cam.depthIm[c[0],c[1]] = 50				

			cv2.imshow('Correspondence label,probability',
						np.hstack([ (px_label*mask[box])/float(px_label.max()),
									np.max(px_corr, -1)]
						))


			cv2.imshow('feature label,probability', 
						np.hstack([ (px_label*mask[box])/float(px_label.max()),
									np.max(px_feature, -1)/float(np.max(px_feature, -1).max())]
						))

			if 0:
				subplot(2,2,1)
				scatter(skel_current[:,1], skel_current[:,2]);
				for i,c in enumerate(constraint_links):
					plot([skel_current[c[0],1], skel_current[c[1],1]],[skel_current[c[0],2], skel_current[c[1],2]])
				axis('equal')

				subplot(2,2,3)
				scatter(skel_current[:,1], -skel_current[:,0]); 
				for i,c in enumerate(constraint_links):
					plot([skel_current[c[0],1], skel_current[c[1],1]],[-skel_current[c[0],0], -skel_current[c[1],0]])
				axis('equal')

				subplot(2,2,4)
				scatter(skel_current[:,2], -skel_current[:,0]); 
				for i,c in enumerate(constraint_links):
					plot([skel_current[c[0],2], skel_current[c[1],2]],[-skel_current[c[0],0], -skel_current[c[1],0]])
				axis('equal')
				# show()
			
			# ---- Display ----
			if get_color:
				cam.colorIm = display_skeletons(cam.colorIm, skel_img[:,[1,0,2]], (0,255,), skel_type='Ganapathi')
				for i,s in enumerate(skel_img):
					# if not visible_joints[i]:
					if i not in skel_correct:
						c = circle(s[0], s[1], 5)
						cam.colorIm[c[0], c[1]] = (255,0,0)
				# cam.colorIm = display_skeletons(cam.colorIm, world2rgb(skel_init+im_pos_mean, [240,320])[:,[1,0]], skel_type='Ganapathi')
			else:
				cam.depthIm = display_skeletons(cam.depthIm, skel_img[:,[1,0,2]], int(cam.depthIm.max()), skel_type='Ganapathi')

			skel_previous = skel_current.copy()
			# skel_previous = skel_init.copy()

			# ------------------------------------------------------------

			if 1:#visualize:
				# for (x, y, w, h) in faces:
				# 	pt1 = (int(x)+box[1].start, int(y)+box[0].start)
				# 	pt2 = (pt1[0]+int(w), pt1[1]+int(h))
				# 	cv2.rectangle(cam.colorIm, pt1, pt2, (255, 0, 0), 3, 8, 0)				
				# cam2.depthIm = display_skeletons(cam2.depthIm, cam2_skels[0], (max_depth,), skel_type='Low')
				# cam.depthIm = display_skeletons(cam.depthIm, skel_msr_im, (max_depth,), skel_type='Low')
				if len(cam_skels) > 0:
					# skel_msr_im = kinect_to_msr_skel(skel_msr_im)
					# cam.colorIm[:,:,2] = display_skeletons(cam.colorIm[:,:,2], skel_msr_im, (255,), skel_type='Low')
					cam.colorIm[:,:,2] = display_skeletons(cam.colorIm[:,:,2], skel_msr_im, (255,), skel_type='Kinect')
				# cv2.imshow("C", im_color)
				cam.visualize()
				# cam2.visualize()
				# embed()

		frame_count+=1
		print "Frame #{0:d}".format(frame_count)

	if learn:
		# train(ims_rgb, ims_depth, labels)
		embed()

	print 'Done'

if __name__=="__main__":

	parser = optparse.OptionParser()
	parser.add_option('-v', '--visualize', dest='viz', action="store_true", default=False, help='Enable visualization')
	parser.add_option('-l', '--learn', dest='learn', action="store_true", default=False, help='Training phase')
	(opt, args) = parser.parse_args()

	main(visualize=opt.viz, learn=opt.learn)

if 0:

	###
	figure(4)
	names = [joint_names[i] for i in hogs_z_pred.astype(np.int)]
	labels_resized = sm.imresize(hogs_z_pred.reshape([-1, 5]), im.shape, 'nearest')
	matshow(labels_resized/13/10. + im/float(im.max()))
	im_c = cam.colorIm[box[0]]
	# matshow(labels_resized/13/10. + im/float(im.max()))
	matshow(labels_resized/13/10. + im_c[:,:,0]/float(im_c.max()))

	### Find joint label closest to each extrema
	extrema = geodesic_extrema_MPI(cam.depthIm*(mask>0), iterations=3)
	for i,_ in enumerate(extrema):
		# j_pos = skel_msr_im[i]
		j_pos = extrema[i]
		x = j_pos[0]
		y = j_pos[1]
		if x-patch_size/2 >= 0 and x+patch_size/2 < height and y-patch_size/2 >= 0 and y+patch_size/2 < width:
			ims_rgb += [im_color[x-patch_size/2:x+patch_size/2, y-patch_size/2:y+patch_size/2]]
			ims_depth += [im_depth[x-patch_size/2:x+patch_size/2, y-patch_size/2:y+patch_size/2]]
			dists = np.sqrt(np.sum((j_pos - skel_msr_im[:,[1,0]])**2,-1))
			labels += [np.argmin(dists)]

	### Multi-cam
	# cam2 = KinectPlayer(base_dir='./', device=2, bg_subtraction=True, get_depth=True, get_color=True, get_skeleton=True, fill_images=False)

	# Transformation matrix from first to second camera
	# data = pickle.load(open("Registration.dat", 'r'))
	# transform_c1_to_c2 = data['transform']

	# cam2_skels = transform_skels(cam_skels, transform_c1_to_c2, 'image')

	# Update frames
	# cam2.sync_cameras(cam)



# Tracking extra
# if 0:
	# Based on geodesic distance
	# skel_img = world2rgb(skel_current, cam.depthIm.shape) - [box[0].start, box[1].start, 0]
	# skel_img = skel_img.clip([0,0,0], [mask[box].shape[0]-1, mask[box].shape[1]-1, 999])
	# for i,s in enumerate(skel_img):	
	# 	_, geodesic_map = geodesic_extrema_MPI(cam.depthIm[box]*mask[box], centroid=[s[0],s[1]], iterations=1, visualize=True)				
	# 	px_corr[:,:,i] = geodesic_map + (-mask[box])*9999

