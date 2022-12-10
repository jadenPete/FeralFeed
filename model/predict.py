#!/usr/bin/env python

from . import FeralFeedModel

model = FeralFeedModel()

def predict(image, is_batch=False):
	""" See FeralFeedModel.preprocess for the expected input.

	Returns:
		A confidence rating between 0 and 1 inclusively that the given image is a cat.
	"""

	x = FeralFeedModel.preprocess(image if is_batch else [image])
	y = model.model.predict(x, batch_size=4 if is_batch else None)[0]

	return y if is_batch else float(y[0])
