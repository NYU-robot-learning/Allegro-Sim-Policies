# Main script for hand interractions 
import cv2 
#import dexterous_env
import gym
import numpy as np
import os
import torch
import torchvision.transforms as T

from gym import spaces
from openteach_deploy_api import DeployAPI
from openteach.robot.allegro.allegro_kdl import AllegroKDL
from openteach.utils.network import ZMQCameraSubscriber
from PIL import Image as im


from allegro_sim.tactile_data import TactileImage, TactileRepresentation
from allegro_sim.models import init_encoder_info
from allegro_sim.utils import *

class DexterityEnv(gym.Env):
    def __init__(
        self,
        tactile_out_dir ,
		tactile_model_type ,
        host_address = '17.24.71.240',
        camera_num = 0,
        height = 480, 
        width = 480, 
        action_type = 'robot'
    ):
        self.width = width
        self.height = height
        self.view_num = camera_num 

        self.deploy_api = DeployAPI(
            host_address=host_address,
            required_data={'rgb_idxs': [camera_num], 'depth_idxs': []}
        )

        self.set_home_state()

        self._hand = AllegroKDL()
        
        # Get the tactile encoder
        device = torch.device('cuda:1')
        tactile_cfg, tactile_encoder, _ = init_encoder_info(device, tactile_out_dir, 'tactile', model_type=tactile_model_type)
        tactile_img = TactileImage(
            tactile_image_size = tactile_cfg.tactile_image_size, 
            shuffle_type = None
        )
        tactile_repr_dim = tactile_cfg.encoder.tactile_encoder.out_dim if tactile_model_type == 'bc' else tactile_cfg.encoder.out_dim
        self.tactile_repr = TactileRepresentation(
            encoder_out_dim = tactile_repr_dim,
            tactile_encoder = tactile_encoder,
            tactile_image = tactile_img,
            representation_type = 'tdex'
        )

        action_dim=16
        self.action_type = action_type
        self.action_space = spaces.Box(low = np.array([-1]*action_dim,dtype=np.float32), # Actions are 12 + 7
                                        high = np.array([1]*action_dim,dtype=np.float32),
                                        dtype = np.float32)
        self.observation_space = spaces.Dict(dict(
            pixels = spaces.Box(low = np.array([0,0],dtype=np.float32), high = np.array([255,255], dtype=np.float32), dtype = np.float32),
            features = spaces.Box(low = np.array([-1]*16, dtype=np.float32),
                                    high = np.array([1]*16, dtype=np.float32),
                                    dtype = np.float32)
        ))
        
        self.image_subscriber = ZMQCameraSubscriber(
            host = host_address,
            port = 10005 + self.view_num,
            topic_type = 'RGB'
        )
        self.image_transform = T.Compose([ # No normalization just simple cropping
            T.Resize((480,480)),
            T.Lambda(self._crop_transform),
            T.Resize((self.height, self.width)),
            T.ToTensor(),
            T.Normalize(VISION_IMAGE_MEANS, VISION_IMAGE_STDS)
        ]) # We're not normalizing here - we normalize in the reward extraction

        self.visualize_image_transform = T.Compose([
            T.Resize((480,480)),
            T.Lambda(self._crop_transform),
            T.Resize((self.height, self.width))
        ])

    def set_home_state(self):
        raise NotImplementedError # This method should be implemented by every class that inherits this

    def set_up_env(self):
        os.environ["MASTER_ADDR"] = "localhost"
        os.environ["MASTER_PORT"] = "29505"

        torch.distributed.init_process_group(backend='gloo', rank=0, world_size=1)
        torch.cuda.set_device(0)

    def _get_curr_image(self, visualize=True):
        image, _ = self.image_subscriber.recv_rgb_image()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = im.fromarray(image, 'RGB')
        if visualize:
            img = self.visualize_image_transform(image)
            img = np.asarray(img)
        else:
            img = self.image_transform(image)
            img = torch.FloatTensor(img)
        return img # NOTE: This is for environment
    def _crop_transform(self, image):
        return crop_transform(image, camera_view=self.view_num)

    def init_hand(self):
        self.deploy_api.send_robot_action(self.home_state)

    def step(self, action):
        print('action.shape: {}'.format(action.shape))
        try: 
            hand_joint_action = action[:19]
            if self.action_type == 'human': # Then we will not be sending the kinova action 
                self.deploy_api.send_robot_action({
                    'allegro': hand_joint_action
                })
            elif self.action_type == 'robot':
                self.deploy_api.send_robot_action({
                    'allegro': hand_joint_action, 
                    'kinova':  action[-7:]
                })
        except:
            print("IK error")
        
        # Get the observations
        obs = {}
        features_dict = self.deploy_api.get_robot_state()
        obs['features'] = np.concatenate(
            [features_dict['allegro']['position'], features_dict['kinova']],
            axis=0
        )

        obs['pixels'] = self._get_curr_image() # NOTE: Check this - you're returning non normalized things though
        
        sensor_state = self.deploy_api.get_sensor_state()
        tactile_values = sensor_state['xela']['sensor_values']
        with torch.no_grad():
            obs['tactile'] = self.tactile_repr.get(tactile_values)

        reward, done, infos = 0, False, {'is_success': False} 

        return obs, reward, done, infos 

    def render(self, mode='rbg_array', width=0, height=0):
        return self._get_curr_image(visualize=True)

    def reset(self): 
        self.init_hand()
        obs = {}
        features_dict = self.deploy_api.get_robot_state() # NOTE: having the features should be better and faster as well
        obs['features'] = np.concatenate(
            [features_dict['allegro']['position'], features_dict['kinova']],
            axis=0
        )
        obs['pixels'] = self._get_curr_image()
        print("Observation", obs)
        return obs

    

    def get_reward():
        pass

