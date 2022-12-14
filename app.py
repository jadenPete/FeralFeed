import flask
import functools
import io
import json
import numpy as np
import os
from PIL import Image

import db

# We were having some issues with Tensorflow on M1; we won't load the model on that platform
try:
	import model.predict

	model_loaded = True
except ModuleNotFoundError:
	model_loaded = False

class CookieNames:
	TOKEN = "token"

app = flask.Flask(__name__)

app.config['SECRET_KEY'] = "SUPERSECIRTKEY"

def populate_config():
	current_dir = os.path.dirname(os.path.abspath(__file__))

	for filename in ["config_private.json", "config_public.json"]:
		with open(os.path.join(current_dir, filename)) as file:
			content = json.load(file)

			assert isinstance(content, dict)

			for key, value in content.items():
				app.config[key] = value

populate_config()

def authenticated(fn):
	@functools.wraps(fn)
	def result(*args, **kwargs):
		if get_user() is None:
			return flask.redirect(flask.url_for("sign_up", next=flask.request.url))

		return fn(*args, **kwargs)

	return result

@app.teardown_request
def close_db(_):
	if "db" in flask.g:
		flask.g.db.__exit__()


def get_db():
	if "db" not in flask.g:
		flask.g.db = db.Database(app.config)

	return flask.g.db

def get_user():
	if "user" not in flask.g:
		if (token := flask.request.cookies.get(CookieNames.TOKEN)) is None:
			flask.g.user = None
		else:
			flask.g.user = get_db().verify_token(token)

	return flask.g.user

@app.context_processor
def inject_debug():
	return {
		"debug": app.debug
	}

@app.context_processor
def inject_user():
	return {
		"user": get_user()
	}

@app.route("/")
def index():
	if get_user() is None:
		return flask.render_template("landing.html", posts=[post.serialize() for post in get_db().posts()])

	return flask.render_template(
		"feed.html",
		posts=[post.serialize() for post in get_db().posts()],
		tags=[entry.value for entry in db.DatabasePostTag],
		user=get_user().id
	)

@app.route("/about")
def about():
	return flask.render_template("about.html")

@app.route("/contact")
def contact():
	return flask.render_template("contact.html")

@app.route("/image")
def image():
	try:
		image_id = int(flask.request.args["id"])
	except (KeyError, ValueError):
		return "Please include an integer id query parameter.", 400

	if (image_content_type := get_db().image(image_id)) is None:
		return "An image with the given ID doesn't exist.", 404

	return image_content_type[0], 200, {
		"Content-Type": image_content_type[1]
	}


@app.post("/posts")
def create_post_2():
	title = flask.request.form.get("title")

	if not title:
		flask.flash("Title is required", category="error")
	elif "picture" not in flask.request.files:
		flask.flash("Picture is required", category="error")
	else:
		flask.flash("Post Successfully Created", category="success")

		description = flask.request.form.get("description")

		if description == "":
			description = None

		picture = flask.request.files["picture"].stream.read()
		picture_mimetype = flask.request.files["picture"].mimetype

		tags = []

		for tag in db.DatabasePostTag:
			if flask.request.form.get(f"{tag.value}-tag") == "on":
				tags.append(tag)

		if model_loaded:
			picture_np = np.array(Image.open(io.BytesIO(picture)))

			confidence = model.predict.predict(picture_np)
		else:
			confidence = 1

		get_db().create_post(
			get_user().id,
			title,
			description,
			picture,
			picture_mimetype,
			tags,
			confidence
		)

	return flask.redirect(flask.url_for("index"))

@app.get("/settings")
def settings():
	return flask.render_template("settings.html", user_data=get_user().serialize())

@app.route("/sign-in", methods=["GET", "POST"])
def sign_in():
	if flask.request.method == "GET":
		return flask.render_template("auth/sign_in.html")

	username = flask.request.form.get("username")
	password = flask.request.form.get("password")

	if None in (username, password):
		return "Please include the username and password.", 400

	user = get_db().user_with_username(username)

	if user is None or (token := user.verify_password(password)) is None:
		return "Username or password incorrect.", 401

	response = flask.make_response(flask.redirect(flask.url_for("index")))
	response.set_cookie(CookieNames.TOKEN, token)

	return response

@app.route("/sign-out")
def sign_out():
	if (user := get_user()) is not None:
		user.delete_token()

	return flask.redirect(flask.url_for("index"))

@app.route("/sign-up", methods=["GET", "POST"])
def sign_up():
	if flask.request.method == "GET":
		return flask.render_template("auth/sign_up.html")

	username = flask.request.form.get("username")
	password = flask.request.form.get("password")

	if None in (username, password):
		return "Please include the username and password.", 400

	if (user := get_db().create_user(username, password)) is None:
		return "Username is already taken.", 409

	response = flask.make_response(flask.redirect(flask.url_for("index")))
	response.set_cookie(CookieNames.TOKEN, user.create_token())

	return response

@app.post('/change_password')
def change_password():
	username = flask.request.form.get('username')
	password = flask.request.form.get('new-password')

	if (get_user().update_password(username, password)):
		flask.flash('Password successfully changed!')
		return flask.redirect(flask.url_for('sign_out'))
	else:
		flask.flash("New password must be different.", category='error')
		return flask.redirect(flask.url_for('settings'))



@app.route("/comment/<int:post_id>", methods=['GET', 'POST'])
def comment(post_id):
	comments = get_db().post_by_id([post_id])[0].comment_serialize()['comments']
	user_list = get_db().post_by_id([post_id])[0].comment_serialize()['users']
	name_list = [get_db().user_from_id(id) for id in user_list]
	comment_container = [(comments[i], name_list[i]) for i in range(len(user_list))]

	if flask.request.method == 'GET':
		if (get_user() is None):
				return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id([post_id])],
		items=comment_container, user_name='Guest')
		return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id([post_id])],
	items=comment_container,
	user_name=get_user().serialize()['username'])
		
	
	if flask.request.method == 'POST':
		if (get_user() is None):
			flask.flash("You must login to comment", category='error')
			return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id([post_id])],
	items=comment_container, user_name='Guest')
		comment = flask.request.form.get('comment')
		if not comment:
			flask.flash("Comment is required", category='error')
		else:
			get_db().comments(get_user().id, post_id, comment, 10)
			comments = get_db().post_by_id([post_id])[0].comment_serialize()['comments']
			user_list = get_db().post_by_id([post_id])[0].comment_serialize()['users']
			name_list = [get_db().user_from_id(id) for id in user_list]
			comment_container = [(comments[i], name_list[i]) for i in range(len(user_list))]
			return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id([post_id])],
	items=comment_container,
	user_name=get_user().serialize()['username'])
		

	
	