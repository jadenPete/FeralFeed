#!/usr/bin/env python

from __init__ import FeralFeedModel
import dataset

model = FeralFeedModel()

print(model.model.summary())

model.model.evaluate(*dataset.test_dataset(), batch_size=4)
