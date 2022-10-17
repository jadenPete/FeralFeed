#!/usr/bin/env python

import os
import tensorflow as tf

from __init__ import FeralFeedModel
import dataset

model = FeralFeedModel()

print(model.model.summary())

try:
	os.mkdir("weights")
except FileExistsError:
	pass

model.model.fit(
	*dataset.train_dataset(),
	batch_size=4,
	epochs=25,
	callbacks=[
		tf.keras.callbacks.ModelCheckpoint(
			filepath="weights/weights-{epoch:02d}-{val_loss:.2f}.hdf5",
			save_weights_only=True
		)
	],
	validation_data=dataset.test_dataset()
)
