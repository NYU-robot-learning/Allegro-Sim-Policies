import glob
import h5py
import numpy as np
import os
import pickle
import torch

from torchvision.datasets.folder import default_loader as loader
from tqdm import tqdm

# Load human data 
def load_human_data(roots, demos_to_use=[], duration=120):
    roots = sorted(roots)

    keypoint_indices = []
    image_indices = []
    hand_keypoints = {}

    for demo_id,root in enumerate(roots): 
        demo_num = int(root.split('/')[-1].split('_')[-1])
        if (len(demos_to_use) > 0 and demo_num in demos_to_use) or (len(demos_to_use) == 0): # If it's empty then it will be ignored
            with open(os.path.join(root, 'keypoint_indices.pkl'), 'rb') as f:
                keypoint_indices += pickle.load(f)
            with open(os.path.join(root, 'image_indices.pkl'), 'rb') as f:
                image_indices += pickle.load(f)

            # Load the data
            with h5py.File(os.path.join(root, 'keypoints.h5'), 'r') as f:
                hand_keypoints[demo_id] = f['transformed_hand_coords'][()] 

    # Find the total lengths now
    whole_length = len(keypoint_indices)
    desired_len = int((duration / 120) * whole_length)

    data = dict(
        keypoint = dict(
            indices = keypoint_indices[:desired_len],
            values = hand_keypoints
        ),
        image = dict( 
            indices = image_indices[:desired_len]
        )
    )

    return data

# Method to load all the data from given roots and return arrays for it
def load_data(roots, demos_to_use=[], duration=120): # If the total length is equal to 2 hrs - it means we want the whole data
    roots = sorted(roots)

    tactile_indices = [] 
    allegro_indices = []
    allegro_action_indices = [] 
    kinova_indices = []
    image_indices = []
    
    tactile_values = {}
    allegro_tip_positions = {} 
    allegro_joint_positions = {}
    allegro_joint_torques = {}
    allegro_actions = {}
    kinova_states = {}
    end_eff_velocities = {}

    for demo_id,root in enumerate(roots): 
        demo_num = int(root.split('/')[-1].split('_')[-1])
        if (len(demos_to_use) > 0 and demo_num in demos_to_use) or (len(demos_to_use) == 0): # If it's empty then it will be ignored
            # with open(os.path.join(root, 'tactile_indices.pkl'), 'rb') as f:
            #     tactile_indices += pickle.load(f)
            with open(os.path.join(root, 'allegro_indices.pkl'), 'rb') as f:
                allegro_indices += pickle.load(f)
            with open(os.path.join(root, 'allegro_action_indices.pkl'), 'rb') as f:
                allegro_action_indices += pickle.load(f)
            # with open(os.path.join(root, 'kinova_indices.pkl'), 'rb') as f:
            #     kinova_indices += pickle.load(f)
            with open(os.path.join(root, 'image_indices.pkl'), 'rb') as f:
                image_indices += pickle.load(f)

            # Load the data
            with h5py.File(os.path.join(root, 'allegro_fingertip_states.h5'), 'r') as f:
                allegro_tip_positions[demo_id] = f['positions'][()]
            with h5py.File(os.path.join(root, 'allegro_joint_states.h5'), 'r') as f:
                allegro_joint_positions[demo_id] = f['positions'][()]
            with h5py.File(os.path.join(root, 'allegro_commanded_joint_states.h5'), 'r') as f:
                allegro_actions[demo_id] = f['positions'][()] # Positions are to be learned - since this is a position control

    # Find the total lengths now
    whole_length = len(image_indices)
    desired_len = int((duration / 120) * whole_length)
    print("Desired length", desired_len)

    data = dict(
        tactile = dict(
            indices = tactile_indices[:desired_len],
            values = tactile_values
        ),
        allegro_joint_states = dict(
            indices = allegro_indices[:desired_len], 
            values = allegro_joint_positions,
            torques = allegro_joint_torques
        ),
        allegro_tip_states = dict(
            indices = allegro_indices[:desired_len], 
            values = allegro_tip_positions
        ),
        allegro_actions = dict(
            indices = allegro_action_indices[:desired_len],
            values = allegro_actions
        ),
        kinova = dict( 
            indices = kinova_indices[:desired_len], 
            values = kinova_states
        ), 
        image = dict( 
            indices = image_indices[:desired_len]
        )
        # endeffector_velocities= dict(
        #     indices = allegro_indices[:desired_len],
        #     values = end_eff_velocities
        # )
    )

    return data


def get_image_stats(len_image_dataset, image_loader):
    psum    = torch.tensor([0.0, 0.0, 0.0])
    psum_sq = torch.tensor([0.0, 0.0, 0.0])

    # loop through images
    for inputs in tqdm(image_loader):
        psum    += inputs.sum(axis = [0, 2, 3])
        psum_sq += (inputs ** 2).sum(axis = [0, 2, 3])

    # pixel count
    count = len_image_dataset * 480 * 480

    # mean and std
    total_mean = psum / count
    total_var  = (psum_sq / count) - (total_mean ** 2)
    total_std  = torch.sqrt(total_var)

    # output
    print('mean: '  + str(total_mean))
    print('std:  '  + str(total_std))

def load_dataset_image(data_path, demo_id, image_id, view_num, transform=None, as_int=False):
    roots = glob.glob(f'{data_path}/demonstration_*')
    roots = sorted(roots)
    image_root = roots[demo_id]
    image_path = os.path.join(image_root, 'cam_{}_rgb_images/frame_{}.png'.format(view_num, str(image_id).zfill(5)))
    img = loader(image_path)
    if not transform is None:
        img = transform(img)
        img = torch.FloatTensor(img)
    return img

# Taken from https://github.com/NYU-robot-learning/multimodal-action-anticipation/utils/__init__.py#L90
def batch_indexing(input, idx):
    """
    Given an input with shape (*batch_shape, k, *value_shape),
    and an index with shape (*batch_shape) with values in [0, k),
    index the input on the k dimension.
    Returns: (*batch_shape, *value_shape)
    """
    batch_shape = idx.shape
    dim = len(idx.shape)
    value_shape = input.shape[dim + 1 :]
    N = batch_shape.numel()
    assert input.shape[:dim] == batch_shape, "Input batch shape must match index shape"
    assert len(value_shape) > 0, "No values left after indexing"

    # flatten the batch shape
    input_flat = input.reshape(N, *input.shape[dim:])
    idx_flat = idx.reshape(N)
    result = input_flat[np.arange(N), idx_flat]
    return result.reshape(*batch_shape, *value_shape) 