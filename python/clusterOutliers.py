import numpy as np
from multiprocessing import Pool,cpu_count
import pandas as pd
import pyfits
import sklearn
from sklearn import preprocessing
from sklearn.manifold import TSNE
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN, KMeans

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib import colors
import matplotlib.cm as cmx
import matplotlib.gridspec as gridspec
import seaborn as sns
from sklearn.decomposition import PCA

import sys
if sys.version_info[0] < 3:
    import Tkinter as Tk
else:
    import tkinter as Tk

import keplerml
import km_outliers
import db_outliers

class clusterOutliers(object):
    def __init__(self,feats,fitsDir):
        self.data = pd.read_csv(feats,index_col=0)
        if fitsDir[-1]=="/":
            self.fitsDir = fitsDir
        else:
            self.fitsDir = fitsDir+"/"
        self.files = self.data.index
        # Initializing the data and files samples with the first 100 entries.
        self.dataSample = self.data.iloc[:100]
        self.filesSample = self.files[:100]
        self.importedForPlotting = False
        self.sampleGenerated = False
        self.sampleTSNE = False
        
    def read_kepler_curve(self,file):
        """
        Given the path of a fits file, this will extract the light curve and normalize it.
        """
        lc = pyfits.getdata(file)
        t = lc.field('TIME')
        f = lc.field('PDCSAP_FLUX')
        err = lc.field('PDCSAP_FLUX_ERR')

        err = err[np.isfinite(t)]
        f = f[np.isfinite(t)]
        t = t[np.isfinite(t)]
        err = err[np.isfinite(f)]
        t = t[np.isfinite(f)]
        f = f[np.isfinite(f)]
        err = err/np.median(f)
        nf = f / np.median(f)

        return t, nf, err
    
    def randSample(self, numLCs):
        """
        Returns a random sample of numLCs light curves, data returned as an array
        of shape [numLCs,3,len(t)]
        Rerunning this, or randSampleWTabby will replace the previous random sample.
        """
        assert (numLCs <self.files.size),"Number of samples greater than the number of files."
        self.numLCs = numLCs
        print("Creating random file list...")
        self.dataSample = self.data.sample(n=numLCs)
        self.filesSample = self.dataSample.index
        self.sampleGenerated = True
        return self.filesSample
    
    def randSampleWTabby(self, numLCs):
        """
        Returns a random sample of numLCs light curves, data returned as an array
        of shape [numLCs,3,len(t)]
        Rerunning this, or randSample will replace the previous random sample.
        """
        assert (numLCs < len(self.files)),"Number of samples greater than the number of files."
        self.numLCs = numLCs
        print("Creating random file list...")
        self.dataSample = self.data.sample(n=numLCs)

        print("Checking for Tabby...")
        if not self.dataSample.index.str.contains('8462852').any():
            print("Adding Tabby...")
            self.dataSample = self.dataSample.drop(self.dataSample.index[0])
            self.dataSample = self.dataSample.append(self.data[self.data.index.str.contains('8462852')])
        self.filesSample = self.dataSample.index
        self.sampleGenerated = True
        return self.filesSample
    
    def fullQ(self):
        self.filesSample = self.files
        self.dataSample = self.data
        return 
    
    def sample_tsne_fit(self):
        """
        Performs a t-SNE dimensionality reduction on the data sample generated.
        Uses a PCA initialization and the perplexity given, or defaults to 50.
        
        Appends the dataSample dataframe with the t-SNE X and Y coordinates
        Returns tsneX and tsneY
        """
        assert self.sampleGenerated,"Sample has not yet been generated using randSample or randSampleWTabby"
        perplexity=len(self.dataSample)/10
        scaler = preprocessing.StandardScaler().fit(self.dataSample)
        scaledData = scaler.transform(self.dataSample)
        tsne = TSNE(n_components=2,perplexity=perplexity,init='pca',verbose=True)
        tsne_fit=tsne.fit_transform(scaledData)
        self.dataSample['tsne_x'] = tsne_fit.T[0]
        self.dataSample['tsne_y'] = tsne_fit.T[1]
        # Goal is to minimize the KL-Divergence
        if sklearn.__version__ == '0.18.1':
            print("KL-Divergence was %s"%tsne.kl_divergence_ )
        print("Done.")
        self.sampleTSNE = True
        return
    
    def tsne_fit(self,data):
        """
        Performs a t-SNE dimensionality reduction on the data sample generated.
        Uses a PCA initialization and the perplexity given, or defaults to 1/10th the amount of data.
        
        Appends the dataSample dataframe with the t-SNE X and Y coordinates
        Returns tsneX and tsneY
        """
        
        perplexity=len(data)/10
        scaler = preprocessing.StandardScaler().fit(data)
        scaledData = scaler.transform(data)
        tsne = TSNE(n_components=2,perplexity=perplexity,init='pca',verbose=True)
        fit=tsne.fit_transform(scaledData)
        # Goal is to minimize the KL-Divergence
        if sklearn.__version__ == '0.18.1':
            print("KL-Divergence was %s"%tsne.kl_divergence_ )
        print("Done.")
        return fit
    
    def pca_fit(self,data):
        scaler = preprocessing.StandardScaler().fit(data)
        scaledData = scaler.transform(data)
        pca = PCA(n_components=2)
        pca_fit = pca.fit_transform(scaledData)
        return pca_fit
    
    def sample_km_out(self):
        assert self.sampleTSNE,"Sample has not been reduced with sample_tsne_fit yet."
        tsneData = self.dataSample[['tsne_x','tsne_y']]
        clusterLabels = km_outliers.kmeans_w_outliers(tsneData,1)
        self.dataSample['km_cluster']=clusterLabels
        return self.dataSample[self.dataSample.km_cluster==-1].index
    
    def km_out(self,df):
        clusterLabels = km_outliers.kmeans_w_outliers(df,1)
        return clusterLabels
        
    def sample_db_out(self):
        assert self.sampleTSNE,"Sample has not been reduced with sample_tsne_fit yet."
        clusterLabels = db_outliers.dbscan_w_outliers(self.dataSample[['tsne_x','tsne_y']])
        self.dataSample['db_cluster']=clusterLabels
        return self.dataSample[self.dataSample.db_cluster==-1].index
    
    def db_out(self,df):
        clusterLabels = db_outliers.dbscan_w_outliers(df)
        return clusterLabels
    
    def save(self,of=self.feats):
        data.to_csv(of)
        
    def plot_sample(self,df=self.dataSample,pathtofits=self.fitsDir,
                    cluster_method="dbscan",reduction_method="tsne"):
        root = Tk.Tk()
        root.wm_title("Scatter")
        """--- import light curve data ---"""
        files = df.index
        
        if cluster_method == 'dbscan':
            clusterLabels = df.db_cluster
        elif cluster_method == 'kmeans':
            clusterLabels = df.km_cluster
            
        # data is an array containing each data point
        data = np.array(df[['tsne_x','tsne_y']])

        cNorm  = colors.Normalize(vmin=0, vmax=max(clusterLabels))
        scalarMap = cmx.ScalarMappable(norm=cNorm, cmap='jet')
        
        data_out = df[clusterLabels==-1]
        data_cluster = self.dataSample[clusterLabels!=-1]
        files_cluster = data_cluster.index

        if reduction_method='tsne':
            # tsneX has all the x-coordinates
            redX = df.tsne_x
            # tsneY has all the y-coordinates
            redY = df.tsne_y
            
            outX = data_out.tsne_x
            outY = data_out.tsne_y
            files_out = data_out.index

            clusterX = data_cluster.tsne_x
            clusterY = data_cluster.tsne_y
            
        elif reduction_method='pca':
            redX = df.pca_x
            redY = df.pca_y
            
            outX = data_out.pca_x
            outY = data_out.pca_y
            files_out = data_out.index
            
            clusterX = data_cluster.pca_x
            clusterY = data_cluster.pca_y

        """--- Organizing data and Labels ---"""


        if df.index.str.contains('8462852').any():
            tabbyInd = list(df.index).index(df[df.index.str.contains('8462852')].index[0])            
        else:
            tabbyInd = 0
            
        fig = Figure(figsize=(20,10))

        # a tk.DrawingArea
        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        # Toolbar to help navigate the data (pan, zoom, save image, etc.)
        toolbar = NavigationToolbar2TkAgg(canvas, root)
        toolbar.update()
        canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        gs = gridspec.GridSpec(2,6)

        with sns.axes_style("white"):
            # empty subplot for scattered data
            ax = fig.add_subplot(gs[0,:4])
            # empty subplot for lightcurves
            ax2 = fig.add_subplot(gs[1,:])
            # empty subplot for center detail
            ax3 = fig.add_subplot(gs[0,4:])

        def distance(point, event):
            """Return distance between mouse position and given data point

            Args:
                point (np.array): np.array of shape (3,), with x,y,z in data coords
                event (MouseEvent): mouse event (which contains mouse position in .x and .xdata)
            Returns:
                distance (np.float64): distance (in screen coords) between mouse pos and data point
            """
            assert point.shape == (2,), "distance: point.shape is wrong: %s, must be (2,)" % point.shape
            x2,y2 = ax.transData.transform((point[0],point[1]))

            return np.sqrt ((x2 - event.x)**2 + (y2 - event.y)**2)

        def calcClosestDatapoint(XT, event):
            """Calculate which data point is closest to the mouse position.

            Args:
                XT (np.array) - array of points, of shape (numPoints, 2)
                event (MouseEvent) - mouse event (containing mouse position)
            Returns:
                smallestIndex (int) - the index (into the array of points X) of the element closest to the mouse position
            """
            distances = [distance (XT[:,i], event) for i in range(XT.shape[1])]

            return np.argmin(distances)

        def drawData(index):
            # Plots the lightcurve of the point chosen
            ax2.cla()
            f = pathtofits+df.index[index]
            t,nf,err=self.read_kepler_curve(f)

            x=t
            y=nf

            axrange=0.55*(max(y)-min(y))
            mid=(max(y)+min(y))/2
            yaxmin = mid-axrange
            yaxmax = mid+axrange
            if yaxmin < .95:
                if yaxmax > 1.05:
                    ax2.set_ylim(yaxmin,yaxmax)
                else:
                    ax2.set_ylim(yaxmin,1.05)
            elif yaxmax > 1.05:
                ax2.set_ylim(.95,yaxmax)
            else:
                ax2.set_ylim(.95,1.05)

            if files[index] in files_cluster:
                color = 'blue'
            else:
                color = 'red'
            ax2.plot(x, y, 'o',markeredgecolor='none', c=color, alpha=0.2)
            ax2.plot(x, y, '-',markeredgecolor='none', c=color, alpha=0.7)
            #ax2.set_title(files[index][:13],fontsize = 20)
            ax2.set_xlabel('Time (Days)',fontsize=22)
            ax2.set_ylabel(r'$\frac{\Delta F}{F}$',fontsize=30)

            fig.suptitle(files[index][:13],fontsize=30)

            canvas.draw()

        def annotatePt(XT, index):
            """Create popover label in 3d chart

            Args:
                X (np.array) - array of points, of shape (numPoints, 3)
                index (int) - index (into points array X) of item which should be printed
            Returns:
                None
            """
            x2, y2 = XT[index][0], XT[index][1]
            # Either update the position, or create the annotation
            if hasattr(annotatePt, 'label'):
                annotatePt.label.remove()
                annotatePt.emph.remove()
            if hasattr(annotatePt, 'emphCD'):
                annotatePt.emphCD.remove()

            # Get data point from array of points X, at position index
            annotatePt.label = ax.annotate( "",
                xy = (x2, y2), xytext = (x2+10, y2+10),
                arrowprops = dict(headlength=20,headwidth=20,width=6,shrink=.1,color='red'))
            annotatePt.emph = ax.scatter(x2,y2,marker='o',s=50,c='red')
            if files[index] in files_cluster:
                annotatePt.emphCD = ax3.scatter(x2,y2,marker='o',s=150,c='red')
            else:
                annotatePt.emphCD = ax.scatter(x2,y2,marker='o',s=50,c='red')
            canvas.draw()


        def onMouseClick(event, X):
            """Event that is triggered when mouse is clicked. Shows lightcurve for data point closest to mouse."""
            XT = np.array(X.T) # array organized by feature, each in it's own array
            closestIndex = calcClosestDatapoint(XT, event)
            drawData(closestIndex)

        def onMouseRelease(event, X):
            XT = np.array(X.T)
            closestIndex = calcClosestDatapoint(XT, event)
            annotatePt(X,closestIndex)
            #for centerIndex in centerIndices:
            #    annotateCenter(XT,centerIndex)

        def connect(X):
            if hasattr(connect,'cidpress'):
                fig.canvas.mpl_disconnect(connect.cidpress)
            if hasattr(connect,'cidrelease'):
                fig.canvas.mpl_disconnect(connect.cidrelease)

            connect.cidpress = fig.canvas.mpl_connect('button_press_event', lambda event: onMouseClick(event,X))
            connect.cidrelease = fig.canvas.mpl_connect('button_release_event', lambda event: onMouseRelease(event, X))

        def redraw():       
            # Clear the existing plots
            ax.cla()
            ax2.cla()
            ax3.cla()
            # Set those labels
            ax.set_xlabel("T-SNE X",fontsize=18)
            ax.set_ylabel("T-SNE Y",fontsize=18)
            # Scatter the data
            ax.scatter(outX, outY,c="black",s=30,cmap='jet')

            ax.hexbin(clusterX,clusterY,mincnt=5,bins="log",cmap="inferno",gridsize=35)
            hb = ax3.hexbin(clusterX,clusterY,mincnt=5,bins="log",cmap="inferno",gridsize=35)
            cb = fig.colorbar(hb)
            """
            ax.scatter(clusterX,clusterY,s=30,c='g')
            ax3.scatter(clusterX,clusterY)
            """
            ax3.set_title("Center Density Detail")
            ax3.set_xlabel("T-SNE X",fontsize=18)
            ax3.set_ylabel("T-SNE Y",fontsize=18)

            #for centerIndex in centerIndices:
            #    annotateCenter(currentData1,centerIndex)

            if hasattr(redraw,'cidenter'):
                    fig.canvas.mpl_disconnect(redraw.cidenter)
                    fig.canvas.mpl_disconnect(redraw.cidexit)
            connect(data)

            annotatePt(data,tabbyInd)

            drawData(tabbyInd)
            #fig.savefig('Plots/Q16_PCA_kmeans/Tabby.png')
            canvas.draw()
            canvas.show()
        print("Plotting.")
        redraw()            
            
        def _delete_window():
            print("window closed.")
            root.destroy()
            sys.exit()
    
        root.protocol("WM_DELETE_WINDOW",_delete_window)
        root.mainloop()