import argon2
import datetime
import psycopg2
import uuid

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
	confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1)
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

	def create_Comment(self, user_Id, title, body, image_Id, catnip, timestamp):


		
		self.cur.execute(
			"INSERT INTO posts (user_Id, title, body, image_Id, catnip, timestamp) VALUES (%s, %s, %s,%s,%s,%s) RETURNING id;",

			(user_Id, title, body, image_Id, catnip, timestamp)


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

	def user_with_username(self, username):
		self.cur.execute("SELECT id FROM users WHERE username = %s;", (username,))

		if self.cur.rowcount > 0:
			return DatabaseUser(self, self.cur.fetchone()[0])

	def verify_token(self, token):
		self.cur.execute("DELETE FROM tokens WHERE expiration < NOW();")

		self.cur.execute("SELECT user_id FROM tokens WHERE uuid = %s;", (token,))

		if self.cur.rowcount > 0:
			return DatabaseUser(self, self.cur.fetchone()[0])

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
