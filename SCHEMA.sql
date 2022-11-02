CREATE TABLE IF NOT EXISTS users (
	id SERIAL PRIMARY KEY,
	username TEXT UNIQUE NOT NULL,
	password BYTEA NOT NULL	
);

CREATE TABLE IF NOT EXISTS images (
	id SERIAL PRIMARY KEY,
	content BYTEA NOT NULL,
	confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS posts (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL REFERENCES users,
	title TEXT NOT NULL,
	body TEXT,
	image_id INTEGER NOT NULL REFERENCES images,
	catnip INTEGER NOT NULL DEFAULT 0,
	timestamp TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS comments (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL REFERENCES users,
	post_id INTEGER NOT NULL REFERENCES posts,
	content TEXT NOT NULL,
	catnip INTEGER NOT NULL DEFAULT 0
);