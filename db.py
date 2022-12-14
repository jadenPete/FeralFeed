import argon2
import datetime
import enum
import flask
import psycopg2
import uuid

class DatabasePostTag(enum.Enum):
	GREY = "grey"
	BLACK = "black"
	WHITE = "white"
	BABY = "baby"
	BIG = "big"

class Database:
	def __init__(self, app_config):
		self.app_config = app_config

		self.conn = psycopg2.connect(self.app_config["psycopg2_dsn"])
		self.conn.autocommit = True
		self.cur = self.conn.cursor()

		self.ph = argon2.PasswordHasher()

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS users (
	id SERIAL PRIMARY KEY,
	username TEXT UNIQUE NOT NULL,
	password BYTEA NOT NULL
);"""
		)

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS tokens (
	uuid UUID PRIMARY KEY,
	user_id INTEGER UNIQUE NOT NULL REFERENCES users,
	expiration TIMESTAMP WITH TIME ZONE NOT NULL
);"""
		)

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS images (
	id SERIAL PRIMARY KEY,
	content BYTEA NOT NULL,
	content_type TEXT NOT NULL,
	confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1)
);"""
		)

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS posts (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL REFERENCES users,
	title TEXT NOT NULL,
	body TEXT,
	image_id INTEGER NOT NULL REFERENCES images,
	catnip INTEGER NOT NULL DEFAULT 0,
	timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);"""
		)

		try:
			self.cur.execute(
				"CREATE TYPE post_tag AS ENUM ('grey', 'black', 'white', 'baby', 'big');"
			)
		except psycopg2.errors.DuplicateObject:
			pass

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS post_tags (
	post_id INTEGER NOT NULL REFERENCES posts,
	tag post_tag NOT NULL,
	PRIMARY KEY (post_id, tag)
);"""
		)

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS comments (
	id SERIAL PRIMARY KEY,
	user_id INTEGER REFERENCES users,
	post_id INTEGER NOT NULL REFERENCES posts,
	content TEXT NOT NULL,
	catnip INTEGER NOT NULL DEFAULT 0
);"""
		)

	def __exit__(self):
		self.cur.close()
		self.conn.close()

	def create_post(self, user_id, title, body, image_content, image_content_type, tags, confidence):
		self.cur.execute(
			"""
INSERT INTO images (content, content_type, confidence)
	VALUES (%s, %s, %s)
	RETURNING id;""", (image_content, image_content_type, confidence)
		)

		self.cur.execute(
			"""
INSERT INTO posts
	(user_id, title, body, image_id, catnip, timestamp)
	VALUES (%s, %s, %s, %s, 0 , NOW()) RETURNING id;""" ,
			(user_id, title, body, self.cur.fetchone()[0])
		)

		post_id = self.cur.fetchone()[0]

		for tag in tags:
			self.cur.execute("INSERT INTO post_tags VALUES (%s, %s);", (post_id, tag.value))

		return DatabasePost(self, post_id)

	def create_user(self, username, password):
		try:
			self.cur.execute(
				"INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id;",

				(username, self.ph.hash(password))
			)

			return DatabaseUser(self, self.cur.fetchone()[0])
		except psycopg2.errors.UniqueViolation:
			pass

	def image(self, id_):
		self.cur.execute("SELECT content, content_type FROM images WHERE id = %s;", (id_,))

		if self.cur.rowcount > 0:
			row = self.cur.fetchone()

			return bytes(row[0]), row[1]

	def post_by_id(self, id_):
		self.cur.execute("SELECT FROM posts WHERE id = %s;", (id_,))

		if self.cur.rowcount == 0:
			return

		return DatabasePost(self, id_)

	def posts(self):
		self.cur.execute("SELECT id FROM posts ORDER BY timestamp DESC;")

		return [DatabasePost(self, row[0]) for row in self.cur.fetchall()]

	def user_with_username(self, username):
		self.cur.execute("SELECT id FROM users WHERE username = %s;", (username,))

		if self.cur.rowcount > 0:
			return DatabaseUser(self, self.cur.fetchone()[0])

	def user_from_id(self, id):
		self.cur.execute("SELECT username FROM users WHERE id = %s", (id,))

		return DatabaseUser(self, self.cur.fetchone()[0]).id

	def verify_token(self, token):
		self.cur.execute("DELETE FROM tokens WHERE expiration < NOW();")

		self.cur.execute("SELECT user_id FROM tokens WHERE uuid = %s;", (token,))

		if self.cur.rowcount > 0:
			return DatabaseUser(self, self.cur.fetchone()[0])

class DatabaseComment:
	def __init__(self, db, id_):
		self.db: Database = db
		self.id = id_

	def serialize(self):
		self.db.cur.execute("SELECT user_id, content FROM comments WHERE id = %s;", (self.id,))

		user_id, content = self.db.cur.fetchone()

		return {
			"username": "Guest" \
				if user_id is None \
				else DatabaseUser(self.db, user_id).serialize()["username"],

			"content": content
		}

class DatabasePost:
	def __init__(self, db, id_):
		self.db: Database = db
		self.id = id_

	def comments(self):
		self.db.cur.execute("SELECT id FROM comments WHERE post_id = %s;", (self.id,))

		return [DatabaseComment(self.db, row[0]) for row in self.db.cur.fetchall()]

	def create_comment(self, user_id, content):
		self.db.cur.execute(
			"""
INSERT INTO comments (user_id, post_id, content, catnip)
	VALUES (%s, %s, %s, 0)
	RETURNING id;""", (user_id, self.id, content))

		return DatabaseComment(self.db, self.db.cur.fetchone()[0])

	def downpurr(self):
		self.db.cur.execute("UPDATE posts SET catnip = catnip - 1 WHERE id = %s;", (self.id,))

	def serialize(self):
		self.db.cur.execute(
			"""
SELECT posts.user_id, username, title, body, confidence, catnip, timestamp, image_id
	FROM posts
	JOIN users ON user_id = users.id
	JOIN images ON image_id = images.id
	WHERE posts.id = %s;""", (self.id,)
		)

		post_row = self.db.cur.fetchone()

		self.db.cur.execute("SELECT tag FROM post_tags WHERE post_id = %s;", (self.id,))

		tag_rows = self.db.cur.fetchall()

		return {
			"user_id": post_row[0],
			"username": post_row[1],
			"title": post_row[2],
			"body": post_row[3],
			"tags": [row[0] for row in tag_rows],
			"catnip": round(post_row[4] * post_row[5]),
			"timestamp": post_row[6],
			"image_url": flask.url_for("image", id=post_row[7]),
			"id": self.id
		}

	def uppurr(self):
		self.db.cur.execute("UPDATE posts SET catnip = catnip + 1 WHERE id = %s;", (self.id,))

class DatabaseUser:
	def __init__(self, db, id_):
		self.db: Database = db
		self.id = id_

	def create_token(self):
		token = str(uuid.uuid4())

		ttl = datetime.timedelta(**self.db.app_config["token_ttl"])

		self.db.cur.execute(
			"""
INSERT INTO tokens
	VALUES (%s, %s, NOW() + %s)
	ON CONFLICT (user_id)
		DO UPDATE SET uuid = EXCLUDED.uuid, expiration = EXCLUDED.expiration;""",
			(token, self.id, ttl)
		)

		return token

	def delete_token(self):
		self.db.cur.execute("DELETE FROM tokens WHERE user_id = %s;", (self.id,))

	def remove_post(self, post_id):
		self.db.cur.execute("SELECT user_id FROM posts WHERE id = %s;", (post_id,))

		if self.db.cur.rowcount == 0:
			return

		if self.db.cur.fetchone()[0] != self.id:
			return False

		self.db.cur.execute("DELETE FROM comments WHERE post_id = %s;", (post_id,))
		self.db.cur.execute("DELETE FROM post_tags WHERE post_id = %s", (post_id,))
		self.db.cur.execute("DELETE FROM posts WHERE id = %s;", (post_id,))

		return True

	def serialize(self):
		self.db.cur.execute("SELECT username FROM users WHERE id = %s", (self.id,))

		return {
			"id": self.id,
			"username" : self.db.cur.fetchone()[0]
		}

	def update_password(self, password):
		self.db.cur.execute(
			"UPDATE users SET password = %s WHERE id = %s", (self.db.ph.hash(password), self.id)
		)

		return True

	def verify_password(self, password):
		self.db.cur.execute("SELECT password FROM users WHERE id = %s;", (self.id,))

		try:
			self.db.ph.verify(bytes(self.db.cur.fetchone()[0]), password)

			return self.create_token()
		except argon2.exceptions.VerifyMismatchError:
			pass
