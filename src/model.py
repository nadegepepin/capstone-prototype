import numpy as np
import logging

import tensorflow as tf
from keras import layers
from keras.layers import Input, Add, Dense, Activation, ZeroPadding2D, BatchNormalization, Lambda 
from keras.layers import Flatten, Conv2D, MaxPooling2D, AveragePooling2D, Reshape, LSTM, Embedding, TimeDistributed
from keras.models import Model, load_model
from keras.preprocessing import image
from keras.initializers import glorot_uniform
from keras.optimizers import Adam
import keras.backend as K

import preprocessing


def identity_block(X, f, filters, stage, block):
    """
    Implementation of the identity block as defined in Figure 4
    
    Arguments:
    X -- input tensor of shape (m, n_H_prev, n_W_prev, n_C_prev)
    f -- integer, specifying the shape of the middle CONV's window for the main path
    filters -- python list of integers, defining the number of filters in the CONV layers of the main path
    stage -- integer, used to name the layers, depending on their position in the network
    block -- string/character, used to name the layers, depending on their position in the network
    
    Returns:
    X -- output of the identity block, tensor of shape (n_H, n_W, n_C)
    """
    
    # defining name basis
    conv_name_base = 'res' + str(stage) + block + '_branch'
    bn_name_base = 'bn' + str(stage) + block + '_branch'
    
    # Retrieve Filters
    F1, F2, F3 = filters
    
    # Save the input value. You'll need this later to add back to the main path. 
    X_shortcut = X
    
    # First component of main path
    X = Conv2D(filters = F1, kernel_size = (1, 1), strides = (1,1), padding = 'valid', name = conv_name_base + '2a', kernel_initializer = glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis = 3, name = bn_name_base + '2a')(X)
    X = Activation('relu')(X)
    
    # Second component of main path
    X = Conv2D(filters = F2, kernel_size = (f, f), strides = (1,1), padding = 'same', name = conv_name_base + '2b', kernel_initializer = glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis = 3, name = bn_name_base + '2b')(X)
    X = Activation('relu')(X)

    # Third component of main path
    X = Conv2D(filters = F3, kernel_size = (1, 1), strides = (1,1), padding = 'valid', name = conv_name_base + '2c', kernel_initializer = glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis = 3, name = bn_name_base + '2c')(X)

    # Final step: Add shortcut value to main path, and pass it through a RELU activation
    X = Add()([X_shortcut , X])
    X = Activation('relu')(X)

    return X



def convolutional_block(X, f, filters, stage, block, s = 2):
    """
    Implementation of the convolutional block as defined in Figure 4
    
    Arguments:
    X -- input tensor of shape (m, n_H_prev, n_W_prev, n_C_prev)
    f -- integer, specifying the shape of the middle CONV's window for the main path
    filters -- python list of integers, defining the number of filters in the CONV layers of the main path
    stage -- integer, used to name the layers, depending on their position in the network
    block -- string/character, used to name the layers, depending on their position in the network
    s -- Integer, specifying the stride to be used
    
    Returns:
    X -- output of the convolutional block, tensor of shape (n_H, n_W, n_C)
    """
    
    # defining name basis
    conv_name_base = 'res' + str(stage) + block + '_branch'
    bn_name_base = 'bn' + str(stage) + block + '_branch'
    
    # Retrieve Filters
    F1, F2, F3 = filters
    
    # Save the input value
    X_shortcut = X

    ##### MAIN PATH #####
    # First component of main path 
    X = Conv2D(F1, kernel_size = (1, 1), strides = (s,s), padding = 'valid', name = conv_name_base + '2a', kernel_initializer = glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis = 3, name = bn_name_base + '2a')(X)
    X = Activation('relu')(X)
    
    # Second component of main path
    X = Conv2D(F2, kernel_size = (f, f), strides = (1,1), padding = 'same', name = conv_name_base + '2b', kernel_initializer = glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis = 3, name = bn_name_base + '2b')(X)
    X = Activation('relu')(X)

    # Third component of main path
    X = Conv2D(F3, kernel_size = (1, 1), strides = (1,1), padding = 'valid', name = conv_name_base + '2c', kernel_initializer = glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis = 3, name = bn_name_base + '2c')(X)

    ##### SHORTCUT PATH ####
    X_shortcut = Conv2D(F3, kernel_size = (1, 1), strides = (s,s), padding = 'valid', name = conv_name_base + '1', kernel_initializer = glorot_uniform(seed=0))(X_shortcut)
    X_shortcut = BatchNormalization(axis = 3, name = bn_name_base + '1')(X_shortcut)

    # Final step: Add shortcut value to main path, and pass it through a RELU activation
    X = Add()([X_shortcut , X])
    X = Activation('relu')(X)
    
    return X



def TrainShowAndTell(caption_max_size, hidden_size, emb_size, image_shape = (300, 300, 3)):
    """
    -- CNN Encoder --
    -----------------
    Implementation of ResNet50:
    CONV2D -> BATCHNORM -> RELU -> MAXPOOL -> CONVBLOCK -> IDBLOCK*2 -> CONVBLOCK -> IDBLOCK*3
    -> CONVBLOCK -> IDBLOCK*5 -> CONVBLOCK -> IDBLOCK*2 -> AVGPOOL -> TOPLAYER
    
    -- RNN Decoder --
    -----------------
    LSTM model with hidden_size activation layers.
    
    Arguments:
    caption_max_size: the max number of tokens of a caption
    hidden_size: activation layer size for LSTM
    emb_size: -- number of features for each token (embedding size)
    input_shape -- shape of the images of the dataset

    Returns:
    model -- a keras model
    """
    ################
    # CNN ENCODER
    ################
        
    # Define the input as a tensor with shape input_shape
    X_input = Input(image_shape, name="image_input")

    # Zero-Padding
    X = ZeroPadding2D((3, 3))(X_input)
    
    # Stage 1
    X = Conv2D(64, (7, 7), strides = (2, 2), name = 'conv1', kernel_initializer = glorot_uniform(seed=0))(X)
    X = BatchNormalization(axis = 3, name = 'bn_conv1')(X)
    X = Activation('relu')(X)
    X = MaxPooling2D((3, 3), strides=(2, 2))(X)

    # Stage 2
    X = convolutional_block(X, f = 3, filters = [64, 64, 256], stage = 2, block='a', s = 1)
    X = identity_block(X, 3, [64, 64, 256], stage=2, block='b')
    #X = identity_block(X, 3, [64, 64, 256], stage=2, block='c')

    # Stage 3 
    X = convolutional_block(X, f = 3, filters = [128,128,512], stage = 3, block='a', s = 2)
    X = identity_block(X, 3, [128,128,512], stage=3, block='b')
    #X = identity_block(X, 3, [128,128,512], stage=3, block='c')
    #X = identity_block(X, 3, [128,128,512], stage=3, block='d')
    
    # Stage 4
    X = convolutional_block(X, f = 3, filters = [256, 256, 1024], stage = 4, block='a', s = 2)
    X = identity_block(X, 3, [256, 256, 1024], stage=4, block='b')
    #X = identity_block(X, 3, [256, 256, 1024], stage=4, block='c')
    #X = identity_block(X, 3, [256, 256, 1024], stage=4, block='d')
    #X = identity_block(X, 3, [256, 256, 1024], stage=4, block='e')
    #X = identity_block(X, 3, [256, 256, 1024], stage=4, block='f')
    
    # Stage 5
    X = convolutional_block(X, f = 3, filters = [512, 512, 2048], stage = 5, block='a', s = 2)
    X = identity_block(X, 3, [512, 512, 2048], stage=5, block='b')
    #X = identity_block(X, 3, [512, 512, 2048], stage=5, block='c')
    
    # AVGPOOL
    X = AveragePooling2D(pool_size=(2, 2), name='avg_pool')(X)

    # output layer
    X = Flatten()(X)
    
    # Insert two FC layers to capture the final features and resize output for injection into the RNN decoder    
    X = Dense(8192, activation='relu', input_shape=(32384,), name = 'dense_img_features')(X)
    X = Dense(emb_size, activation='relu', use_bias = False, name = 'dense_img_final_features')(X)

    ################
    # RNN DECODER
    ################
    
    # Redefine the input (features) layer's shape
    X = Lambda(lambda x : K.expand_dims(x, axis=1))(X)    

    # Define the initial hidden state a0 and initial cell state c0
    a0 = Input(shape=(hidden_size,), name='a0')
    c0 = Input(shape=(hidden_size,), name='c0')
    print(a0.shape)
    # Take image embedding as the first input to LSTM
    LSTMLayer = LSTM(hidden_size, return_sequences = True, return_state = True, dropout=0.5, name = 'lstm')
    print(X.shape)
    X, a, c = LSTMLayer(X, initial_state=[a0, c0])

    # Text embedding    
    caption = Input(shape=(caption_max_size, emb_size), name="caption_input")
    #X_caption = Embedding(vocab_size, emb_size, mask_zero = True, name = 'emb_text')(caption)
    print(caption.shape)
    
    # Take image embedding as the first input to LSTM
    C, _, _ = LSTMLayer(caption, initial_state=[a, c])
    output = TimeDistributed(Dense(emb_size, activation='softmax'), name = 'output')(C)
    print(output.shape)
    
    return Model(inputs=[X_input, caption, a0, c0], outputs=output, name='TrainShowAndTell')


