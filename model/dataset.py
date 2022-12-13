import numpy as np
import tensorflow_datasets as tfds

from . import FeralFeedModel

dataset, info = tfds.load("oxford_iiit_pet", shuffle_files=True, with_info=True)

def preprocess_dataset(name):
	for i, species in enumerate(info.features["species"].names):
		if species == "Cat":
			cat_id = i

			break

	x, y = [], []

	for datum in dataset[name]:
		x.append(datum["image"])
		y.append(datum["species"])

	result_x = FeralFeedModel.preprocess(x)
	result_y = (
		np.array([[individual_species] for individual_species in y]) == cat_id
	).astype(np.float32)

	return result_x, result_y

def train_dataset():
	return preprocess_dataset("train")

def test_dataset():
	return preprocess_dataset("test")
