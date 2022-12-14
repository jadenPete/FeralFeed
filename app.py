import flask
import functools
import io
import json
import math
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

def index_posts(post_id, tag_filter, ordering):
	posts = [post.serialize() for post in get_db().posts()]

	if post_id is not None:
		posts = [post for post in posts if post["id"] == post_id]

	if tag_filter is not None:
		posts = [post for post in posts if any(tag == tag_filter for tag in post["tags"])]

	if ordering not in (None, "favorited"):
		if ordering == "top":
			key = lambda post: post["catnip"]
		elif ordering == "new":
			key = lambda post: -post["timestamp"].timestamp()
		elif ordering == "rising":
			key = index_reddit_hot_key

		posts.sort(key=key)

	return posts

def index_reddit_hot_key(serialized_post):
	# https://medium.com/hacking-and-gonzo/how-reddit-ranking-algorithms-work-ef111e33d0d9
    sign = 1 if serialized_post["catnip"] > 0 else -1 if serialized_post["catnip"] < 0 else 0

    order = math.log10(max(abs(serialized_post["catnip"]), 1))

    seconds = serialized_post["timestamp"].timestamp() - 1134028003

    return round(sign * order + seconds / 45000, 7)

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

@app.route("/about")
def about():
	return flask.render_template("about.html")

@app.post("/password")
def change_password():
	username = flask.request.form.get("username")
	password = flask.request.form.get("new-password")

	if (get_user().update_password(password)):
		flask.flash("Password successfully changed!")
		return flask.redirect(flask.url_for("sign_out"))
	else:
		flask.flash("New password must be different.", category="error")
		return flask.redirect(flask.url_for("settings"))

@app.route("/contact")
def contact():
	return flask.render_template("contact.html")

@app.post("/posts")
def create_post():
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

@app.post("/posts/<int:post_id>/delete")
def delete_post(post_id):
	if (authorized := get_user().remove_post(post_id)) is None:
		return "That post doesn't exist.", 404

	if not authorized:
		return "You didn't create that post.", 401

	return flask.redirect(flask.url_for("index"))

@app.get("/posts/<int:post_id>/downpurr")
def downpurr(post_id):
	if (post := get_db().post_by_id(post_id)) is None:
		return "That post doesn't exist.", 404

	post[0].downpurr()

	return flask.redirect(flask.url_for("index"))

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

@app.route("/")
def index():
	posts = index_posts(
		flask.request.args.get("post_id", type=int),
		flask.request.args.get("filter"),
		flask.request.args.get("sort")
	)

	trending_posts = index_posts(None, None, "rising")

	tags = [entry.value for entry in db.DatabasePostTag]

	if get_user() is None:
		return flask.render_template(
			"landing.html",
			posts=posts,
			trending_posts=trending_posts,
			tags=tags
		)

	return flask.render_template(
		"feed.html",
		posts=posts,
		trending_posts=trending_posts,
		tags=tags,
		user=get_user().serialize()
	)

@app.get("/settings")
def settings():
	return flask.render_template("settings.html",user_data=get_user().serialize())

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

@app.route("/thankyou")
def thankyou():
	return flask.render_template("thankyou.html")

	if (get_user().update_password(username, password)):
		flask.flash('Password successfully changed!')
		return flask.redirect(flask.url_for('sign_out'))
	else:
		flask.flash("New password must be different.", category='error')
		return flask.redirect(flask.url_for('settings'))

@app.get("/posts/<int:post_id>/uppurr")
def uppurr(post_id):
	if (post := get_db().post_by_id(post_id)) is None:
		return "That post doesn't exist.", 404

	post.uppurr()

	return flask.redirect(flask.url_for("index"))

@app.route("/posts/<int:post_id>/comments", methods=['GET', 'POST'])
def comment(post_id):
	comments = get_db().post_by_id(post_id)[0].comment_serialize()['comments']
	user_list = get_db().post_by_id(post_id)[0].comment_serialize()['users']
	name_list = [get_db().user_from_id(id).id for id in user_list]
	comment_container = [(comments[i], name_list[i]) for i in range(len(user_list))]

	if flask.request.method == 'GET':
		if (get_user() is None):
				return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id(post_id)],
		items=comment_container, user_name='Guest')
		return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id(post_id)],
	items=comment_container,
	user_name=get_user().serialize()['username'])


	if flask.request.method == 'POST':
		if (get_user() is None):
			flask.flash("You must login to comment", category='error')
			return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id(post_id)],
	items=comment_container, user_name='Guest')
		comment = flask.request.form.get('comment')
		if not comment:
			flask.flash("Comment is required", category='error')
		else:
			get_db().comments(get_user().id, post_id, comment, 10)
			comments = get_db().post_by_id(post_id)[0].comment_serialize()['comments']
			user_list = get_db().post_by_id(post_id)[0].comment_serialize()['users']
			name_list = [get_db().user_from_id(id).id for id in user_list]
			comment_container = [(comments[i], name_list[i]) for i in range(len(user_list))]

			return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id([post_id])],
	items=comment_container,
	user_name=get_user().serialize()['username'])

	return flask.render_template("comments.html", posts=[post.serialize() for post in get_db().post_by_id([post_id])])
