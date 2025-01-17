# -*- coding: utf-8 -*-
"""
Created on Tue Feb 28 16:40:08 2017

@author: fankai
"""

import tensorflow as tf
import numpy as np
import tensorflow.contrib.layers as tcl
#import csv
import os
#from scipy import stats
#import pdb
import peakutils
#from peakutils.plot import plot as pplot

os.environ["CUDA_VISIBLE_DEVICES"]="0"
tf.reset_default_graph()

def rmse(predictions, targets):
    return np.sqrt(((predictions - targets) ** 2).mean())


class Model(object):
    
    def __init__(self, train_mode=True, input_dim=25, T=150, prev=16,
                 lstm_size=256,
                 batch_size=100, e_learning_rate=1e-4,
                 ):
        self.train_mode = train_mode
        self.input_dim = input_dim
        self.T = T
        self.prev = prev

        self.enc_size = lstm_size        
        
        self.batch_size = batch_size
        self.e_learning_rate = e_learning_rate

        self._srng = np.random.RandomState(np.random.randint(1,2147462579))
        
        self.lstm_enc = tf.contrib.rnn.LSTMCell(self.enc_size, state_is_tuple=True)
        
        # initial state
        self.enc_state = self.lstm_enc.zero_state(self.batch_size, tf.float32)
        self.ys = [0] * self.T
        self.y_prev = 0.0
        self.e_loss = 0.0
        
        # build computation graph of model
        self.DO_SHARE=None
        self.x = tf.placeholder(tf.float32, shape=[self.batch_size, self.input_dim])
        self.ymax = tf.placeholder(tf.float32, shape=[self.batch_size, 1])
        self.y = tf.placeholder(tf.float32, shape=[self.batch_size, self.T])
        
        xe = self.input_embedding(self.x)
        self.h = self.height_model(xe)
        self.p_loss = tf.reduce_mean(tf.square(self.h - self.ymax))
        self.e_loss += self.p_loss
        
        for t in range(self.T): # range(self.T): if using python3
            
            self.y_prev = self.get_yprev(t)
            h_enc, self.enc_state = self.encode(self.enc_state, tf.concat([xe, self.y_prev], 1))
            ylt = self.linear(h_enc)
            self.ys[t] = tf.sigmoid(ylt)
            y_true = tf.reshape(self.y[:,t], [-1, 1])
            self.e_loss += tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=ylt, labels=y_true))
             
            self.DO_SHARE = True

        self.e_vars = tf.trainable_variables()

        self.e_optimizer = tf.train.AdamOptimizer(self.e_learning_rate, beta1=0.5, beta2=0.999)
        e_grads = self.e_optimizer.compute_gradients(self.e_loss, self.e_vars)
        clip_e_grads = [(tf.clip_by_norm(grad, 5), var) for grad, var in e_grads if grad is not None]
        self.e_optimizer = self.e_optimizer.apply_gradients(clip_e_grads)

        
#        if self.train_mode == False:
#            self.sess = tf.Session()
#            saver = tf.train.Saver()
#            saver.restore(self.sess, self.model_path + "/mymodel-599") #
#            Lets, Lpts = [], []
#            ysts, hts = [], []
#            ytests, ptests= [], []
#            # code to load test data
#            for xtest, ytest, ptest in self.data_loader(test_set,self.batch_size):
#                ytest=ytest[:,::-1]
#                Let, Lpt, yst, ht = self.sess.run([self.e_loss, self.p_loss, self.ys, self.h], feed_dict={self.x: xtest, self.y: ytest, self.ymax: ptest})
#                Lets.append(Let)
#                Lpts.append(Lpt)
#                try:
#                    ytests = np.concatenate((ytests, ytest), axis=0)
#                    ptests = np.concatenate((ptests, ptest), axis=0)
#                except:
#                    ytests = ytest
#                    ptests = ptest
#                try:
#                    ysts = np.concatenate((ysts, yst), axis=0)
#                    hts= np.concatenate((hts, ht), axis=0)
#                except:
#                    ysts = yst
#                    hts= ht
#
#            Le_test = np.array(Lets).mean()
#            Lp_test = np.array(Lpts).mean()
#            # code save result
#            print("Le: %f Lp: %f " % (Le_test, Lp_test))
#            np.savetxt('yst.txt', ysts )
#            np.savetxt('ht.txt', hts )
#            np.savetxt('ytest.txt', ytests )
#            np.savetxt('ptest.txt', ptests )
#            self.sess.close()
            
    
    def train(self, train_set, valid_set, maxEpoch=10):
        
         with tf.Session() as sess:
            
            saver = tf.train.Saver()
            sess.run(tf.global_variables_initializer())
            
            i = 0
            for epoch in range(maxEpoch): # range for python3
                
                for xtrain, ytrain, ptrain in self.data_loader(train_set, self.batch_size, shuffle=True):
                    ytrain = ytrain[:,::-1]
                    
                    _, Le, Lp, ys, h = sess.run([self.e_optimizer, self.e_loss, self.p_loss, self.ys, self.h], 
                                     feed_dict={self.x: xtrain, self.y: ytrain, self.ymax: ptrain})
                    i += 1
                    
                    if i % 10 == 0:
                        Levs, Lpvs = [], []
                        for xvalid, yvalid, pvalid in self.data_loader(valid_set, self.batch_size):
                            yvalid = yvalid[:,::-1]
                            
                            Lev, Lpv, ysv, hv = sess.run([self.e_loss, self.p_loss, self.ys, self.h], feed_dict={self.x: xvalid, self.y: yvalid, self.ymax: pvalid})
                            Levs.append(Lev)
                            Lpvs.append(Lpv)
                        Le_valid = np.array(Levs).mean()
                        Lp_valid = np.array(Lpvs).mean()
                        print("Iter=%d: Le: %f Lp: %f Le_valid: %f Lp_valid: %f" % (i, Le, Lp, Le_valid, Lp_valid))
                        #print(ys)
                        #print(h)

                
                self.save_model(saver, sess, step=epoch)
#                np.savetxt('ys_epoch'+str(epoch)+'.txt', ys )
#                np.savetxt('ytrain_epoch'+str(epoch)+'.txt', ytrain )
#                np.savetxt('h_epoch'+str(epoch)+'.txt',h )
#                np.savetxt('ptrain_epoch'+str(epoch)+'.txt',ptrain )
#                np.savetxt('ysv_epoch'+str(epoch)+'.txt', ysv )
#                np.savetxt('yvalid_epoch'+str(epoch)+'.txt', yvalid )
#                np.savetxt('hv_epoch'+str(epoch)+'.txt',hv )
#                np.savetxt('pvalid_epoch'+str(epoch)+'.txt',pvalid )  
    
    def data_loader(self, train_set, batchsize, shuffle=False): 
        features, labels, peaks = train_set
        if shuffle:
            indices = np.arange(len(features))
            self._srng.shuffle(indices)
        for start_idx in range(0, len(features) - batchsize + 1, batchsize):
            if shuffle:
                excerpt = indices[start_idx:start_idx + batchsize]
            else:
                excerpt = slice(start_idx, start_idx + batchsize)
            yield features[excerpt], labels[excerpt], peaks[excerpt]
            
    def data_loader2(self, test_set, batchsize, shuffle=False): 
        for start_idx in range(0, len(test_set) - batchsize + 1, batchsize):
            excerpt = slice(start_idx, start_idx + batchsize)
            yield test_set[excerpt]
        
    
    def save_model(self, saver, sess, step):
        """
        save model with path error checking
        """
        if self.model_path is None:
            my_path = "save" # default path in tensorflow saveV2 format
            # try to make directory if "save" path does not exist
            if not os.path.exists("save"):
                try:
                    os.makedirs("save")
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise
        else: 
            my_path = self.model_path + "/mymodel"
                
        saver.save(sess, my_path, global_step=step)
    
    
    def encode(self, state, input):
        """
        run LSTM
        state = previous encoder state
        input = cat(read,h_dec_prev)
        returns: (output, new_state)
        """
        with tf.variable_scope("e_lstm",reuse=self.DO_SHARE):
            return self.lstm_enc(input,state)
            
    #fully_connected creates a variable called weights,
    #representing a fully connected weight matrix, which is multiplied by the inputs to produce a Tensor of hidden units
    def linear(self, x):
        with tf.variable_scope("e_linear", reuse=self.DO_SHARE):
            yl = tcl.fully_connected(inputs=x, num_outputs=1, activation_fn=None)
        return yl # output logits w.r.t sigmoid
    
    def input_embedding(self, x):
        with tf.variable_scope("e_eblinear1", reuse=None):
            h1 = tcl.fully_connected(inputs=x, num_outputs=128, activation_fn=tf.nn.relu)
        with tf.variable_scope("e_eblinear2", reuse=None):
            h2 = tcl.fully_connected(inputs=x, num_outputs=64, activation_fn=tf.nn.relu)
        return h2
    
    def height_model(self, x):
        with tf.variable_scope("e_hlinear1", reuse=None):
            h1 = tcl.fully_connected(inputs=x, num_outputs=64, activation_fn=tf.nn.relu)
        with tf.variable_scope("e_hlinear2", reuse=None):
            h2 = tcl.fully_connected(inputs=x, num_outputs=1, activation_fn=None)
        return h2

    def get_yprev(self, t):
        with tf.variable_scope("e_yprev", reuse=self.DO_SHARE):
            yp_init = tf.get_variable('yp_init', [self.batch_size, self.prev], initializer=tf.constant_initializer(0.5))
        return yp_init if t == 0 else tf.concat([self.y_prev[:,1:], self.ys[t-1]], 1)
            

if __name__ == "__main__":
    
    # TODO: preprocessing dataset
    # Load data from csv file


    
    bsize=100
    sample_size=10000000
    iter_num=int(sample_size/bsize)-1
    center=501
    ceter_edge=25
    length=2*center-1
    x_axis=np.linspace(0, length, num=length)
    thred_pt=0.1
    mymodel = Model( train_mode=False, input_dim=13, T=501, batch_size=bsize)
    saver = tf.train.Saver()
    
    for iters in range(iter_num):
        saved_matrix1=np.zeros((bsize,4))
        saved_matrix2=np.zeros((bsize,4))
        saved_matrix3=np.zeros((bsize,505))
        #randomly generating input parameter combinations 
        G4=0.5*np.ones((bsize,1))#np.random.rand(sample_size,1)+1e-5
        alpha=0.5*np.ones((bsize,1))#np.random.rand(sample_size,1)
        beta=0.5*np.ones((bsize,1))#np.random.rand(sample_size,1)
        Kphi=0.3*np.ones((bsize,1))#np.random.rand(sample_size,1)+1e-5
        exp_phi=0.5*np.ones((bsize,1))#np.random.rand(sample_size,1)
        alpha_c=np.random.rand(bsize,1)*(1-0.04)+0.04
        alpha_T=0.8*np.ones((bsize,1))#np.random.rand(sample_size,1)*(1-0.01)+0.01
        alpha_L=0.3*np.ones((bsize,1))#np.random.rand(sample_size,1)*(1-0.01)+0.01
        KC=0.5*np.ones((bsize,1))#np.random.rand(sample_size,1)*(1-0.25)+0.25
        KT=np.random.rand(bsize,1)*(1-0.01)+0.01
        KP=0.5*np.ones((bsize,1))#np.random.rand(sample_size,1)*(1-0.01)+0.01
        d_A=0.5*np.ones((bsize,1))#np.random.rand(sample_size,1)*(1-0.025)+0.025
        domainR=1.0*np.ones((bsize,1))#np.random.rand(sample_size,1)*(1-0.34)+0.34#np.random.randint(1,7,size=(sample_size,1))*0.4/3+0.2
        
        test_set = np.concatenate((G4, alpha, beta, Kphi, exp_phi, alpha_c, alpha_T, alpha_L, KC, KT, KP, d_A, domainR), axis=1)
  
        with tf.Session() as sess:
            saver.restore(sess, "saved_model_13"+"/mymodel-499j1_new") 
            yst1, ht1 = sess.run([mymodel.ys,mymodel.h], feed_dict={mymodel.x: test_set})
    
        #pdb.set_trace() 
        with tf.Session() as sess:        
            saver.restore(sess, "saved_model_13"+"/mymodel-499j2_new") #
            yst2, ht2= sess.run([mymodel.ys,mymodel.h], feed_dict={mymodel.x: test_set})
    
        with tf.Session() as sess:        
            saver.restore(sess, "saved_model_13"+"/mymodel-499j3_new") #
            yst3,ht3 = sess.run([mymodel.ys,mymodel.h], feed_dict={mymodel.x: test_set})
        
        with tf.Session() as sess:        
            saver.restore(sess, "saved_model_13"+"/mymodel-499j4_new") #
            yst4, ht4= sess.run([mymodel.ys,mymodel.h], feed_dict={mymodel.x: test_set})
                
    
        m_all=np.zeros((sample_size, 4))
        mse_gt=np.zeros((sample_size, 1))
        idxs=np.zeros((sample_size, 2))
        eps=1e-20
        
        for kb in range(bsize):
    #        array1=ysts1[:,kb,0]/max(ysts1[:,kb,0])
    #        array2=ysts2[:,kb,0]/max(ysts2[:,kb,0])
    #        array3=ysts3[:,kb,0]/max(ysts3[:,kb,0])
    #        array4=ysts4[:,kb,0]/max(ysts4[:,kb,0])
            array1=np.squeeze(yst1)[:,kb]
            array2=np.squeeze(yst2)[:,kb]
            array3=np.squeeze(yst3)[:,kb]
            array4=np.squeeze(yst4)[:,kb]
            
            m1=(rmse(array1, array2)+rmse(array1, array3)+rmse(array1, array4))/3
            m2=(rmse(array2, array1)+rmse(array2, array3)+rmse(array2, array4))/3
            m3=(rmse(array3, array1)+rmse(array3, array2)+rmse(array3, array4))/3 
            m4=(rmse(array4, array1)+rmse(array4, array2)+rmse(array4, array3))/3
            
            mall=[m1, m2, m3, m4]
            mdiv=np.mean(mall)
            
            #if mdiv>0.06:
            #    continue
                
            
            idx2=mall.index(min(mall))+1
            arr2='array'+str(idx2)
            
            final_pred=eval(arr2)
            full_distr=np.concatenate((final_pred[:-1], np.flipud(final_pred)), axis=0)
            
            
            indexes = peakutils.indexes(full_distr, thres=0.1, min_dist=50)
            indexes2 = peakutils.indexes(full_distr, thres=0.1, min_dist=1)
            indexes3 = peakutils.indexes(1-full_distr,thres=0.01, min_dist=5)
            mask = np.ones(len(indexes2), dtype=bool)
            mask3 = np.ones(len(indexes3), dtype=bool)
            
            
            nn=sum(abs(indexes-center)<ceter_edge); #number of peaks near the center
            nn2=sum(abs(indexes2-center)<ceter_edge); #number of peaks near the center      
    
            if np.logical_and(nn2>1,nn==1): #if two peaks are too close to the center, treat it as one and the minimal in between is deleted
                idx=np.where(abs(indexes2-center)<ceter_edge)
    
                #filter out minimal locs between the first peak and last peak within center_edge
                idx3=np.where((indexes3>indexes2[idx[0][0]]) & (indexes3<indexes2[idx[0][-1]]))
                mask3[idx3[0]] = False
    
                for n1 in range(nn2): #remove the fake peaks within center region
                    if indexes2[idx[0][n1]] not in indexes:
                        mask[idx[0][n1]] = False
                indexes2 = indexes2[mask]
                indexes3=indexes3[mask3]
                
            mask = np.ones(len(indexes2), dtype=bool) 
            mask2 = np.ones(len(indexes2), dtype=bool) 
            mask3 = np.ones(len(indexes3), dtype=bool)       
            for n in range(len(indexes2)):
                if  indexes2[n] not in indexes:
                    mask[n]=False
            
            for n in range(len(indexes2)-1):#valley between two fake peaks are deleted
                if np.logical_and(mask[n]==False, mask[n+1]==False): 
                    idx3=np.where((indexes3>indexes2[n]) & (indexes3<indexes2[n+1]))
                    if len(idx3[0]):
                        if min(full_distr[indexes3[idx3[0]]])>min(full_distr[indexes3]):
                            mask3[idx3[0]]=False
                            mask2[n]=False
                            mask2[n+1]=False
            indexes2 = indexes2[mask2]
            indexes3=indexes3[mask3]
            mask = np.ones(len(indexes2), dtype=bool) 
            mask2 = np.ones(len(indexes2), dtype=bool) 
            mask3 = np.ones(len(indexes3), dtype=bool)  
            for n in range(len(indexes2)):
                if  indexes2[n] not in indexes:
                    mask[n]=False    
            
            for n in range(len(indexes2)-1): #remove the minimal values between fake peaks and real peaks
                if np.logical_and(mask[n]==False, mask[n+1]==True):
                    idx3=np.where((indexes3>indexes2[n]) & (indexes3<indexes2[n+1]))
                    mask3[idx3[0]]=False
                    mask2[n]=False
            indexes2 = indexes2[mask2]            
            indexes3=indexes3[mask3]
        
            mask = np.ones(len(indexes2), dtype=bool) 
            mask2 = np.ones(len(indexes2), dtype=bool) 
            mask3 = np.ones(len(indexes3), dtype=bool)  
            for n in range(len(indexes2)):
                if  indexes2[n] not in indexes:
                    mask[n]=False    
            
            for n in range(len(indexes2)-1): #remove the minimal values between fake peaks and real peaks
                if np.logical_and(mask[n]==True, mask[n+1]==False):
                    idx3=np.where((indexes3>indexes2[n]) & (indexes3<indexes2[n+1]))
                    mask3[idx3[0]]=False
                    mask2[n+1]=False
            indexes2 = indexes2[mask2]            
            indexes3=indexes3[mask3]    
            
            mask4 = np.ones(len(indexes3), dtype=bool)
            
        
            for ss in range(len(indexes3)):  
                if (full_distr[indexes3[ss]-1]+full_distr[indexes3[ss]+1]-2*full_distr[indexes3[ss]])/2>0.1:
                    mask4[ss]=False  #minimal peaks cannot be too narrow
            
            indexes3=indexes3[mask4]        
    
            mask2 = np.ones(len(indexes3), dtype=bool)
            max_val=full_distr[indexes]
            prominence=np.zeros(len(indexes))
            if np.logical_and(len(indexes3),len(indexes)):#calculate the prominence of each peak based on the adjancent minimal point, if the prominence of a peak is less than 0.1, it cannot be observed due to small size, ignore the peak
                min_val=full_distr[indexes3]
                for k2 in range(len(indexes)):
                    prominence[k2]=max_val[k2]-min_val[np.argmin(np.absolute(indexes3-indexes[k2]))]
                indexes_temp=indexes[prominence>=thred_pt]
                removed_indexes=indexes[prominence<thred_pt]
                removed_boo=prominence<thred_pt
                if sum(removed_boo)>1: #if two adjancent peaks both have small prominence, reduce one, and delete the valley between them and recalculate the prominence again
                    
                    not_removed_boo=np.ones(len(indexes), dtype=bool)
                    for rr in range(len(removed_boo)-1):
                        if np.logical_and(removed_boo[rr]==1, removed_boo[rr+1]==1):
                            idx2=np.where((indexes3>indexes[rr]) & (indexes3<indexes[rr+1]))
                            if not len(idx2[0]): #if no minimal points between two peaks
                                not_removed_boo[rr]=False #remove point rr
                            else:
                                pt1=max(full_distr[indexes[rr]]-full_distr[indexes3[idx2[0]]])
                                pt2=max(full_distr[indexes[rr+1]]-full_distr[indexes3[idx2[0]]])
                                if np.logical_and(pt1<thred_pt,pt2<thred_pt): #if the valley in between is shallow, delete the valley as well as the peak on the left
                                    mask2[idx2[0]]=False
                                    not_removed_boo[rr]=False #remove point rr
        
                    indexes3=indexes3[mask2]
                    indexes_temp=indexes[not_removed_boo]
                    prominence2=np.zeros(len(indexes_temp))
                    if np.logical_and(len(indexes3),len(indexes_temp)):#calculate the prominence of each peak based on the adjancent minimal point, if the prominence of a peak is less than 0.1, it cannot be observed due to small size, ignore the peak
                        min_val=full_distr[indexes3]
                        max_val=full_distr[indexes_temp]
                        for k3 in range(len(indexes_temp)):
                            prominence2[k3]=max_val[k3]-min_val[np.argmin(np.absolute(indexes3-indexes_temp[k3]))]
                        indexes_temp=indexes_temp[prominence2>=0.1]
            
                            
                
                if not len(indexes_temp): #if indexes_temp is empty
                    indexes_temp=[indexes[np.argmin(np.absolute(indexes-center))]]
                
                indexes=indexes_temp
            
        
        
            #calculate whether distribution has patterns (local_peak_n=0 no pattern, >0, has pattern
            if np.logical_or(not len(indexes), np.any(full_distr<0)):
                 local_peak_n=0
            else:
                local_peak_n=len(indexes)
                
            if local_peak_n<=1:
                saved_matrix1[kb,:]=np.r_[test_set[kb,5], test_set[kb,9], local_peak_n, mdiv]
            elif 1<local_peak_n<=3:
                saved_matrix2[kb,:]=np.r_[test_set[kb,5], test_set[kb,9], local_peak_n, mdiv]
            else:
                saved_matrix3[kb,:]=np.r_[test_set[kb,5], test_set[kb,9], np.transpose(final_pred), local_peak_n, mdiv]
            #print("kb=%f" % (kb))
            #pdb.set_trace()
        indices1 = [i for (i,v) in enumerate(saved_matrix1[:,0]) if v==0]
        a1 = np.delete(saved_matrix1, indices1, 0)
        indices2 = [i for (i,v) in enumerate(saved_matrix2[:,0]) if v==0]
        a2 = np.delete(saved_matrix2, indices2, 0)
        indices3 = [i for (i,v) in enumerate(saved_matrix3[:,0]) if v==0]
        a3 = np.delete(saved_matrix3, indices3, 0)
        with open('output/saved_matrix1_13_10000000_610.txt', 'ab') as fd1:
            np.savetxt(fd1, a1)  
            fd1.flush()
        with open('output/saved_matrix2_13_10000000_610.txt', 'ab') as fd2:
            np.savetxt(fd2, a2)
            fd2.flush()
        with open('output/saved_matrix3_13_10000000_610.txt', 'ab') as fd3:
            np.savetxt(fd3, a3)   
            fd3.flush()
