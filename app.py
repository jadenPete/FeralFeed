import flask
import functools
import json
import os

import db

class CookieNames:
	TOKEN = "token"



app = flask.Flask(__name__)
app.config['SECRET_KEY'] = 'super secret key'

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
		return flask.render_template("landing.html")

	return flask.render_template("feed.html", posts=[post.serialize() for post in get_db().posts()])

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


@app.post("/create_post")
def create_post():
	title = flask.request.form.get("title", type=str)
	description = flask.request.form.get("description", type=str)
	picture = flask.request.form.get("picture")
	user_id = get_user().id
	

	if not title:
		flask.flash("Title is required", category='error')
	elif not picture:
		flask.flash("Picture is required", category='error')
	else:
		flask.flash("Post Successfully Created", category='success')
		get_db().create_post(user_id,title,description, picture, "image/png")
		

	return flask.redirect(flask.url_for("index"))