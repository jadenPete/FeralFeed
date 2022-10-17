import numpy as np
import os
import tensorflow as tf

class FeralFeedModel:
	image_size = [128, 128]

	def __init__(self):
		self.model = tf.keras.models.Sequential([
			tf.keras.layers.Conv2D(16, 3, padding="same", input_shape=(*self.image_size, 3)),
			tf.keras.layers.LeakyReLU(),
			tf.keras.layers.MaxPooling2D(),
			tf.keras.layers.Dropout(0.2),
			tf.keras.layers.LeakyReLU(),
			tf.keras.layers.Conv2D(32, 3, padding="same"),
			tf.keras.layers.LeakyReLU(),
			tf.keras.layers.MaxPooling2D(),
			tf.keras.layers.Dropout(0.2),
			tf.keras.layers.Conv2D(64, 3, padding="same"),
			tf.keras.layers.LeakyReLU(),
			tf.keras.layers.MaxPooling2D(),
			tf.keras.layers.Dropout(0.2),
			tf.keras.layers.Conv2D(128, 3, padding="same"),
			tf.keras.layers.LeakyReLU(),
			tf.keras.layers.MaxPooling2D(),
			tf.keras.layers.Dropout(0.2),
			tf.keras.layers.Flatten(),
			tf.keras.layers.Dense(64),
			tf.keras.layers.LeakyReLU(),
			tf.keras.layers.Dropout(0.2),
			tf.keras.layers.Dense(32),
			tf.keras.layers.LeakyReLU(),
			tf.keras.layers.Dropout(0.2),
			tf.keras.layers.Dense(1),
			tf.keras.layers.Activation("sigmoid")
		])

		self.model.compile(
			optimizer="adam",
			loss="binary_crossentropy",
			metrics=["binary_accuracy"]
		)

		script_dir = os.path.dirname(os.path.realpath(__file__))

		for filename in os.listdir(script_dir):
			if filename.startswith("final-weights") and filename.endswith(".hdf5"):
				self.model.load_weights(os.path.join(script_dir, filename))

				break

	@classmethod
	def preprocess(cls, x):
		""" Preprocesses a list of variable-sized images with pixel values between 0 and 255.

		Returns:
			A batch suitable for input directly into the TensorFlow model.
		"""

		return np.array([
			tf.image.resize(np.array(image, dtype=np.float32) / 255, cls.image_size)

			for image in x
		])
