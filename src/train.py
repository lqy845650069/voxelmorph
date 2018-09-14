"""
train atlas-based alignment with voxelmorph
"""

# python imports
import os
import glob
import sys
import random
from argparse import ArgumentParser

# third-party imports
import tensorflow as tf
import numpy as np
from keras.backend.tensorflow_backend import set_session
from keras.optimizers import Adam
from keras.models import load_model, Model

# project imports
import datagenerators
import networks
import losses


vol_size = (160, 192, 224)  #Volume size used in our experiments. Please change to suit your data.
base_data_dir = '/data/vision/polina/projects/ADNI/work/neuron/data/t1_mix/proc/resize256-crop_x32/'
train_vol_names = glob.glob(base_data_dir + 'train/vols/*.npz')
# random.shuffle(train_vol_names)

atlas = np.load('../data/atlas_norm.npz')
atlas_vol = atlas['vol']
atlas_vol = np.reshape(atlas_vol, (1,) + atlas_vol.shape + (1,))


def train(model, save_name, gpu_id, lr, n_iterations, reg_param, model_save_iter):
    """
    model training function
    :param model: either vm1 or vm2 (based on CVPR 2018 paper)
    :param save_name: name of models being trained
    :param gpu_id: integer specifying the gpu to use
    :param lr: learning rate
    :param n_iterations: number of training iterations
    :param reg_param: the smoothness/reconstruction tradeoff parameter (lambda in CVPR paper)
    :param model_save_iter: frequency with which to save models
    """
    model_dir = '../models/' + save_name
    if not os.path.isdir(model_dir):
        os.mkdir(model_dir)

    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config.allow_soft_placement = True
    set_session(tf.Session(config=config))

    # UNET filters for voxelmorph-1 and voxelmorph-2
    nf_enc = [16, 32, 32, 32]
    if model == 'vm1':
        nf_dec = [32, 32, 32, 32, 8, 8]
    else:
        nf_dec = [32, 32, 32, 32, 32, 16, 16]

    model = networks.unet(vol_size, nf_enc, nf_dec)
    model.compile(optimizer=Adam(lr=lr), loss=[
        losses.cc3D(), losses.gradientLoss('l2')], loss_weights=[1.0, reg_param])
    # model.load_weights('../models/udrnet2/udrnet1_1/120000.h5')

    batch_size = 1  # Can be larger, but depends on GPU memory and volume size
    train_example_gen = datagenerators.example_gen(train_vol_names)
    zero_flow = np.zeros((batch_size,) + (vol_size[0:3]) + (3,))

    for step in range(0, n_iterations):

        X = train_example_gen.__next__()[0]
        train_loss = model.train_on_batch(
            [X, atlas_vol], [atlas_vol, zero_flow])

        if not isinstance(train_loss, list):
            train_loss = [train_loss]

        print_loss(step, 1, train_loss)

        if step % model_save_iter == 0:
            model.save(model_dir + '/' + str(step) + '.h5')


def print_loss(step, training, train_loss):
    """
    Prints training progress to std. out
    :param step: iteration number
    :param training: a 0/1 indicating training/testing
    :param train_loss: model loss at current iteration
    """
    s = str(step) + "," + str(training)

    if isinstance(train_loss, list) or isinstance(train_loss, np.ndarray):
        for i in range(len(train_loss)):
            s += "," + str(train_loss[i])
    else:
        s += "," + str(train_loss)

    print(s)
    sys.stdout.flush()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--model", type=str, dest="model",
                        choices=['vm1', 'vm2'], default='vm2',
                        help="Voxelmorph-1 or 2")
    parser.add_argument("--save_name", type=str, required=True,
                        dest="save_name", help="Name of model when saving")
    parser.add_argument("--gpu", type=int, default=0,
                        dest="gpu_id", help="gpu id number")
    parser.add_argument("--lr", type=float,
                        dest="lr", default=1e-4, help="learning rate")
    parser.add_argument("--iters", type=int,
                        dest="n_iterations", default=150000,
                        help="number of iterations")
    parser.add_argument("--lambda", type=float,
                        dest="reg_param", default=1.0,
                        help="regularization parameter")
    parser.add_argument("--checkpoint_iter", type=int,
                        dest="model_save_iter", default=5000,
                        help="frequency of model saves")

    args = parser.parse_args()
    train(**vars(args))
