from flask import Flask, render_template, redirect

app = Flask(__name__)

@app.route("/")
def index():
	# TODO: Serve the landing page if the user isn't logged in

	return render_template("feed.html")

@app.route("/about")
def about():
	return render_template("about.html")

@app.route("/contact")
def contact():
	return render_template("contact.html")

@app.route("/landing")
def landing():
	return render_template("landing.html")

@app.get("/login")
def login():
	return render_template("login.html")

@app.post("/login")
def post_login():
	return redirect('/feed')