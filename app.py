import flask

app = flask.Flask(__name__)

@app.route("/")
def index():
	# TODO: Serve the landing page if the user isn't logged in

	return flask.render_template("feed.html")

@app.route("/about")
def about():
	return flask.render_template("about.html")

@app.route("/contact")
def contact():
	return flask.render_template("contact.html")

@app.route("/landing")
def landing():
	return flask.render_template("landing.html")
