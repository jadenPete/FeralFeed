import argon2
import datetime
import enum
import flask
import psycopg2
import uuid

class DatabasePostTag(enum.Enum):
	"Grey" = 0
	"Black" = 1
	"White" = 2
	"Baby" = 3
	"Big" = 4


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

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS post_tags (
	post_id INTEGER NOT NULL REFERENCES posts,
	tag INTEGER NOT NULL,
	PRIMARY KEY (post_id, tag_id)
);"""
		)

		self.cur.execute(
			"""
CREATE TABLE IF NOT EXISTS comments (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL REFERENCES users,
	post_id INTEGER NOT NULL REFERENCES posts,
	content TEXT NOT NULL,
	catnip INTEGER NOT NULL DEFAULT 0
);"""
		)

	def __exit__(self):
		self.cur.close()
		self.conn.close()

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

	def posts(self):
		self.cur.execute("SELECT id FROM posts ORDER BY timestamp DESC;")

		return [DatabasePost(self, row[0]) for row in self.cur.fetchall()]

	def user_with_username(self, username):
		self.cur.execute("SELECT id FROM users WHERE username = %s;", (username,))

		if self.cur.rowcount > 0:
			return DatabaseUser(self, self.cur.fetchone()[0])

	def verify_token(self, token):
		self.cur.execute("DELETE FROM tokens WHERE expiration < NOW();")

		self.cur.execute("SELECT user_id FROM tokens WHERE uuid = %s;", (token,))

		if self.cur.rowcount > 0:
			return DatabaseUser(self, self.cur.fetchone()[0])

class DatabasePost:
	def __init__(self, db, id_):
		self.db = db
		self.id = id_

	def serialize():
		self.db.cur.execute(
			"""
SELECT username, title, body, image_id, confidence, catnip, timestamp
	FROM posts WHERE id = %s
	JOIN users WHERE user_id = users.id
	JOIN images WHERE image_id = images.id;""", (self.id,)
		)

		row = self.db.cur.fetchone()

		return {
			"username": row[0],
			"title": row[1],
			"body": row[2],
			"image_url": flask.url_for("image", id=row[3]),
			"catnip": row[4] * row[5],
			"timestamp": row[6]
		}

class DatabaseUser:
	def __init__(self, db, id_):
		self.db = db
		self.id = id_

	def delete_token(self):
		self.db.cur.execute("DELETE FROM tokens WHERE user_id = %s;", (self.id,))

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

	def verify_password(self, password):
		self.db.cur.execute("SELECT password FROM users WHERE id = %s;", (self.id,))

		try:
			self.db.ph.verify(bytes(self.db.cur.fetchone()[0]), password)

			return self.create_token()
		except argon2.exceptions.VerifyMismatchError:
			pass
