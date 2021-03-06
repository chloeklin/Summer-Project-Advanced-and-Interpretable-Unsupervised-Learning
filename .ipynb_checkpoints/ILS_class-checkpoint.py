import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import argrelmax
from scipy.ndimage.filters import gaussian_filter1d
from sklearn.metrics import pairwise_distances
from sklearn.metrics.pairwise import distance_metrics

class ILS():
    """ Iterative Label Spreading

    Parameters
    ----------

    n_clusters : int, default=None
        The number of clusters expected to be identified
        from given dataset.

    min_cluster_size : int, default=None
        The minimum number of data points to be considered as a cluster.

    metric : String, default='euclidean'
        The valid metric for pairwise_distance.
        Must be a metric listed in pairwise.PAIRWISE_DISTANCE_FUNCTIONS or
        an option allowed by scipy.spatial.distance.pdist

    Attributes
    ----------

    dataset : ndarray of shape(n_samples, n_features)
        Transform input dataset into numpy ndarray

    rmin : ndarray of shape(n_samples, )
        The R_min distance of each iteration

    Examples
    ---------
    ##to be added after implementation of find peaks algorithm

    """
    def __init__(self, n_clusters = None, min_cluster_size = None, metric = 'euclidean', plot_rmin = False, sensitivity = 0.1):

        self.n_clusters = n_clusters # need to calculate defaults based on data set input
        self.min_cluster_size = min_cluster_size
        self.metric = metric
        self.plot_rmin = plot_rmin
        self.sensitivity = sensitivity

    def fit(self, X):
        '''
        Main ILS function. Run iteravtive label spreading first to identify peaks to find points of highest density.
        Finally label points given the initial points found from points of highest density.
        INPUT:
            X = data set to be clustered
                numpy 2D array or pandas data frame
        OUTPUT:
            self = returns the ILS object where clustering results are stored.
        '''

        if self.min_cluster_size is None and self.n_clusters is None:
            self.min_cluster_size = int (0.05 * X.shape[0])
        elif self.min_cluster_size is None:
            self.min_cluster_size = int (X.shape[0]/(self.n_clusters * 2)) #currently assumes maximum of 20 clusters

        self.data_set = np.concatenate((np.array(X), np.zeros((X.shape[0],1))), axis = 1)
        self.rmin = []

        self.data_set[0, X.shape[1]] = 1 #initialise first label
        unlabelled = [i + 1 for i in range(X.shape[0] - 1)] # step 1
        
        label_spreading = self.label_spreading([0], unlabelled)
        
        new_centers, new_unlabelled = self.find_initial_points() # step 2
        
        label_spreading = self.label_spreading(new_centers, new_unlabelled, first_run = False) #step 3

        return self

    def find_minima(self):
        '''
        Find index of points that serve as the initial label for the final label spreading. 
        OUTPUT:
            index = list index of r_min plot
        '''
        if self.rmin == []:
            raise Exception("ILS has not been run yet")
        
        # smooth curve        
        filtered = self.rmin[:-self.min_cluster_size//4]
        filtered = self.moving_max(filtered, self.min_cluster_size//16)
        filtered = gaussian_filter1d(filtered, self.min_cluster_size//8)
        filtered[-10] = np.min(filtered)/2 # removing problem of extremely low densities
        filtered = -1 * np.log(filtered)
        filtered = -1 * (filtered - np.min(filtered))/(np.max(filtered) - np.min(filtered))
        filtered = filtered - np.min(filtered)
        index = np.arange(len(filtered))
        fil = filtered

        # find peaks, remove peaks and the beginning and end if implied cluster size is too small

        if self.n_clusters is None:
            maxima = self.find_peaks(filtered, self.min_cluster_size, self.sensitivity)
        else:
            maxima = self.find_peaks(filtered, self.min_cluster_size, 0) 
        
        filtered = gaussian_filter1d(self.rmin, self.min_cluster_size//32)
        filtered = (filtered - np.min(filtered))/(np.max(filtered) - np.min(filtered))

        betweenMax = np.split(filtered, maxima)
        betweenIndex = np.split(index, maxima)        
        
        minima = [np.argmin(betweenMax[i]) + betweenIndex[i][0] for i in range(len(betweenMax))]
        
        lst = [1 if i in maxima else 0 for i in range(len(filtered))]
        lst1 = [1 if i in minima else 0 for i in range(len(filtered))]
        
        if self.plot_rmin == True:
            plt.plot(fil)
            plt.plot(self.rmin)
            plt.plot(filtered)
            plt.plot(lst, c = 'yellow')
            plt.plot(lst1, c = 'red')
            plt.show()
        
        return minima
    
    def prom_widths(self, peak_lst):
        '''
        Given the list of possible peaks calculate the distance between the neighbours. This is then used as the window
        on either side of the peak to calculate the peak prominence. If it is the first peak or last peak we choose a large number
        so that singular peak prominence will use a left or right window size of maximal width.
        INPUTS:
            peak_lst = lst of peak indices (integers)
        OUTPUTS:
            widths = list of tuples of integers. First element and second element in the tuple is the left and right width respectively.
                order corresponds to the order of peaks given.
        '''
        
        widths = []
        
        for i in range(len(peak_lst)):
            if i == 0:
                widths.append((self.data_set.shape[0], peak_lst[i + 1] - peak_lst[i])) 
            elif i == len(peak_lst) - 1:
                widths.append((peak_lst[i] - peak_lst[i-1], self.data_set.shape[0]))
            else:
                widths.append((peak_lst[i] - peak_lst[i-1], peak_lst[i+1] - peak_lst[i]))
        
        return widths
    
    def find_peaks(self, rmin, width, threshold):
        '''
        Find peaks within a given list of doubles. Given a threshold and width find the local maxima
        that have a peak prominence that exceeds the threshold given.
        INPUTS:
            rmin = list of doubles to find peaks in
            width = minimum cluster size
            threshold = smallest peak prominence a peak/local maxima should have
        OUTPUTS:
            pks = index of peaks that have been found
        '''
    
        maxs = argrelmax(np.array(rmin), order = 10)
        
        widths = self.prom_widths(maxs[0])
        
        proms = self.peak_prom(maxs[0], rmin, widths)
        
        pks = []
        if threshold != 0:
            for i in range(len(proms)):
                if proms[i] > threshold:
                    pks.append(maxs[0][i])
        else:
            try:
                inds = np.argpartition(proms, -1 * (self.n_clusters-1))[-1 * (self.n_clusters-1):]
                pks = np.sort(maxs[0][inds]).tolist()
            except:
                raise Exception("There are not {} clusters".format(self.n_clusters))
                            
        return pks
    
    def peak_prom(self, peaks, rmin, windows):
        '''
        Calculate the prominence for a given list of peaks within a list of doubles.
        INPUTS:
            peaks = list of integers indicating the index of the peaks within rmin
            rmin = list of doubles
            window = list of tuples containing left and right width for each peak
        OUPUTS:
            proms = list of peak prominence in the same ordering as the peaks were given
        '''
        
        proms = []
        
        for i in range(len(peaks)):
            proms.append(self.singular_peak_prominence(peaks[i], rmin, windows[i]))
        
        return proms
    
    def singular_peak_prominence(self, peak, rmin, window):
        '''
        Calculate the peak prominence for a given peak. However standardise the input such that the maximum is 1. 
        This means the the prominence of a peak is not a function of its magnitude but rather its magnitude relative to its surroudings.
        Also instead of taking the difference between the maximum and the highest minimum out of left or right we take the smallest 
        minimum on each side. ILS also seeks to detect step changes, this change handles step changes to some extent.
        INPUTS:
            peak = index of of a local maximum to calculate peak prominence for
            rmin = list of floats where the peak exists in
            window = window size for the surroundings the peak should be compared to
        OUTPUTS:
            prominence = the prominence of the given peak (double)
        '''
        left_window = window[0]
        right_window = window[1]
        
        sublst1 = rmin[max([peak - left_window, 0]):peak]
        sublst2 = rmin[peak+1:min([peak + right_window, len(rmin)-1])]

        maxim = max([max(sublst1), max(sublst2)])
        
        min1 = self.mintillmax(np.flip(sublst1, axis = 0), rmin[peak])
        min2 = self.mintillmax(sublst2, rmin[peak])
        
        if min1 is None or min2 is None:
            raise Exception("The peak is not a local maximum")
        
        minimum = min(min1, min2)
        
        return (rmin[peak] - minimum)
    
    def mintillmax(self, sublst, maxthreshold):
        '''
        Given a list and a threshold, find the minimum element until exceeding the threshold.
        If the threshold is exceeded immediately return none as this is not a local maximum
        INPUTS:
            sublst = list to iterate through
            maxthreshold = threshold that triggers the iteration to stop if exceeded
        OUTPUTS:
            minimum = minimum element found
        '''
        minimum = None
        
        for i in range(len(sublst)):
            if sublst[i] > maxthreshold:
                break
            if minimum is None or sublst[i] < minimum:
                minimum = sublst[i]

        return minimum
    
    def moving_max(self, lst, window):
        
        mvmax = [max(lst[i:i+window]) for i in range(len(lst)-window)]
        for i in range(window):
            mvmax.append(mvmax[-1])
            
        return mvmax

    def find_initial_points(self):
        '''
        Finds the points of highest density within the clusters found in the initial run and labels them in seperate classes.
        OUTPUTS:
            labelled_points: indices of labelled points (points of highest density)
                list of integers
            unlabelled_points: indices of ulabelled points (points of highest density)
                list of integers
        '''

        # get points of maximum density
        labelled_points = self.find_minima()

        counter = 1

        # label them in the data_set
        for i in labelled_points:
            self.data_set[self.indOrdering[i], -1] = counter
            counter += 1

        labelled_points = self.indOrdering[labelled_points]

        unlabelled_points = [i for i in range(self.data_set.shape[0]) if not i in labelled_points]

        # check that we haven't missed any points
        if len(unlabelled_points) + len(labelled_points) != self.data_set.shape[0]:
            raise Exception("The number of labelled (0) and unlabelled (0) points does not sum to the total (100) in find_initial_points")

        return labelled_points, unlabelled_points
    
    def create_colr(self, lsts):
        colour = ['red', 'blue', 'gray', 'black', 'orange', 'purple', 'green', 'yellow', 'brown', 'red', 'blue', 'gray', 'black', 'orange', 'purple', 'green', 'yellow', 'brown']
        return [colour[i] for i in lsts]
    
    def predict(self, points):
        '''
        predict takes in an array of points and returns an 1D array of there corresponding labels
        INPUTS:
            points = 2D array of floats
        OUTPUTS:
            labels = 1D array of labels in the same order as th points given.
        '''
        
        D = pairwise_distances(self.data_set[:, :-1], 
                             points,
                             metric = self.metric)
        
        label_points = [np.unravel_index(D[:, i].argmin(), D[:, i].shape) for i in range(points.shape[0])]
        label_points = [label_points[i][0] for i in range(len(label_points))]
        
        return self.data_set[label_points, -1]
    
    def coloured_rmin(self):
        colour = ['red', 'blue', 'gray', 'black', 'orange', 'purple', 'green', 'yellow', 'brown', 'red', 'blue', 'gray', 'black', 'orange', 'purple', 'green', 'yellow', 'brown']
        
        for i in range(len(self.rmin)-2):
            plt.plot([i, i+1], self.rmin[i:i+2], color = colour[self.data_set[self.indOrdering.astype(int)[i], -1].astype(int)], linewidth = 0.8)
        
        plt.show()
        
    
    def plot_labels(self):
        
        plt.scatter(self.data_set[:, 0], self.data_set[:, 1], color = self.create_colr(self.data_set[:, -1].astype(int)),s = 2)
        plt.show()

    def label_spreading(self, labelled_points, unlabelled_points, first_run = True):
        """
        Written by Amanda Parker
        Applies iterative label spreading to the given points
        
        Parameters
        ----------
        labelled_points : ndarray of shape(labelled_num, n_features+1)
            Initial points that are already labelled, the last column indicates the label of the point. 
            0 indicates unlabelled points, positive integers indicate labelled points.
            
        unlabelled_points = ndarray of shape(unlabelled_num, n_features+1)
            Initial points that are not labelled, the last column indicates the label of the point. 
            0 indicates unlabelled points, positive integers indicate labelled points.
            
        Returns
        ---------
        closest : ndarray of shape(n_samples-1, 2)
            Each row indicates the point(in Column 2) where the point's(in Column 1) label is spread from
            Both columns represent points as indices from 
        """
        indices = np.arange(self.data_set.shape[0]) 
        oldIndex = np.arange(self.data_set.shape[0]) 
        
        indOrdering = np.array(labelled_points).reshape(-1,)
        oldIndOrdering = np.array(unlabelled_points).reshape(-1,)
       
        labelled = self.data_set[labelled_points]
        unlabelled = self.data_set[unlabelled_points]
      
        labelColumn = self.data_set.shape[1]-1
        # lists for ordered output data
        outD = []
        outID = []
        closeID = []
    
        count = 0
        # Continue to label data points until all data points are labelled
        while len(unlabelled) > 0 :
            # Calculate labelled to unlabelled distances matrix (D) 
            D = pairwise_distances(
                labelled[:, :-1],
                unlabelled[:, :-1], metric=self.metric)
            # Find the minimum distance between a labelled and unlabelled point
            # first the argument in the D matrix
            (posL, posUnL) = np.unravel_index(D.argmin(), D.shape)
            #append R_min distance
            if first_run:
                self.rmin.append(D.min())
                
            indOrdering = np.concatenate((indOrdering, oldIndOrdering[posUnL].reshape(1,)), axis = 0)
            oldIndOrdering = np.delete(oldIndOrdering, posUnL, axis = 0)
            
            # Switch label from 0 to new label
            unlabelled[posUnL, labelColumn] = labelled[posL,labelColumn] 
            
            # move newly labelled point to labelled dataframe
            labelled = np.concatenate((labelled, unlabelled[posUnL, :].reshape(1,unlabelled.shape[1])), axis=0)
            # drop from unlabelled data frame
            unlabelled = np.delete(unlabelled, posUnL, 0)
            
            # output the distance and id of the newly labelled point
            outID.append(posUnL)
            closeID.append(posL)
            
            
        # Throw error if loose or duplicate points
        if labelled.shape[0] + unlabelled.shape[0] != self.data_set.shape[0] : 
            raise Exception(
                '''The number of labelled ({}) and unlabelled ({}) points does not sum to the total ({})'''.format( len(labelled), len(unlabelled),self.data_set.shape[0]) )
        # Reodered index for consistancy
        newIndex = oldIndex[outID]
        if first_run:
            self.indOrdering = indOrdering
        
        #labelled = labelled[np.argsort(indOrdering), :]
        
        # ID of point label was spread from
        closest = np.concatenate((np.array(newIndex).reshape((-1, 1)), np.array(closeID).reshape((-1, 1))), axis=1)      

        # Add new labels
        newLabels = labelled[:,self.data_set.shape[1]-1]
        #self.data_set[:,self.data_set.shape[1]-1] = newLabels
        self.data_set = labelled[np.argsort(indOrdering)]
        # invert the permutation and then assign the labels
        self.labels = self.data_set[:, -1].copy()
        return closest