BEGIN TRANSACTION;
CREATE TABLE comment (
	id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	user_id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id), 
	FOREIGN KEY(post_id) REFERENCES post (id)
);
INSERT INTO "comment" VALUES(2,'This Bullshit','2026-02-15 18:19:24.228602',2,2);
INSERT INTO "comment" VALUES(3,'Cool resource','2026-02-15 21:48:18.235253',4,2);
CREATE TABLE document (
	id INTEGER NOT NULL, 
	filename VARCHAR(300) NOT NULL, 
	original_filename VARCHAR(300) NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	file_type VARCHAR(50), 
	file_size INTEGER, 
	is_paid BOOLEAN, 
	price FLOAT, 
	uploaded_at DATETIME NOT NULL, 
	download_count INTEGER, 
	PRIMARY KEY (id)
);
INSERT INTO "document" VALUES(1,'dfd910ae3c6a42118a7bfbd96e925c25.pdf','CV.pdf','C:\Users\ANONYMOUS\Downloads\files\edushare-updated\edushare\app/static/uploads\documents\dfd910ae3c6a42118a7bfbd96e925c25.pdf','pdf',41945,0,0.0,'2026-02-15 15:22:24.430259',1);
INSERT INTO "document" VALUES(2,'a4d5158633f54f9ea9ff75a91ea97f41.pdf','Discrete_Math.pdf','C:\Users\ANONYMOUS\Downloads\files\edushare-updated\edushare\app/static/uploads\documents\a4d5158633f54f9ea9ff75a91ea97f41.pdf','pdf',2011484,0,0.0,'2026-02-15 15:52:01.208114',0);
CREATE TABLE followers (
	follower_id INTEGER NOT NULL, 
	followed_id INTEGER NOT NULL, 
	PRIMARY KEY (follower_id, followed_id), 
	FOREIGN KEY(follower_id) REFERENCES user (id), 
	FOREIGN KEY(followed_id) REFERENCES user (id)
);
INSERT INTO "followers" VALUES(2,1);
INSERT INTO "followers" VALUES(4,2);
INSERT INTO "followers" VALUES(5,2);
INSERT INTO "followers" VALUES(5,4);
CREATE TABLE "like" (
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	user_id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT unique_like UNIQUE (user_id, post_id), 
	FOREIGN KEY(user_id) REFERENCES user (id), 
	FOREIGN KEY(post_id) REFERENCES post (id)
);
INSERT INTO "like" VALUES(2,'2026-02-15 18:19:12.546854',2,2);
INSERT INTO "like" VALUES(3,'2026-02-15 21:48:32.238906',4,2);
CREATE TABLE notification (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	message VARCHAR(300) NOT NULL, 
	notification_type VARCHAR(50), 
	link VARCHAR(300), 
	is_read BOOLEAN, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id)
);
CREATE TABLE post (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	user_id INTEGER NOT NULL, 
	subject_id INTEGER, 
	has_document BOOLEAN, 
	document_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id), 
	FOREIGN KEY(subject_id) REFERENCES subject (id), 
	FOREIGN KEY(document_id) REFERENCES document (id)
);
INSERT INTO "post" VALUES(2,'Discrete Mathematics','','2026-02-15 15:52:01.210898','2026-02-15 15:52:01.210904',2,1,1,2);
CREATE TABLE purchase (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	amount_paid FLOAT NOT NULL, 
	payment_method VARCHAR(50), 
	transaction_id VARCHAR(200), 
	status VARCHAR(50), 
	purchased_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id), 
	FOREIGN KEY(document_id) REFERENCES document (id), 
	UNIQUE (transaction_id)
);
CREATE TABLE subject (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	description TEXT, 
	icon VARCHAR(50), 
	color VARCHAR(7), 
	"order" INTEGER, 
	is_active BOOLEAN, 
	created_at DATETIME NOT NULL, 
	post_count INTEGER, 
	PRIMARY KEY (id)
);
INSERT INTO "subject" VALUES(1,'Mathematics & Statistics','mathematics-statistics','Pure Math, Applied Math, Actuarial Science','calculator','#3b82f6',0,1,'2026-02-15 15:50:59.410771',2);
INSERT INTO "subject" VALUES(2,'Computer Science & IT','computer-science-it','Software Engineering, Artificial Intelligence, Cybersecurity, Data Science','code','#3b82f6',0,1,'2026-02-16 00:16:17.965055',0);
INSERT INTO "subject" VALUES(3,'Engineering','engineering','Civil, Mechanical, Electrical, Chemical, Aerospace, Biomedical','compass-drafting','#3b82f6',0,1,'2026-02-16 00:19:17.716213',0);
INSERT INTO "subject" VALUES(4,'Physical Sciences','physical-sciences','Physics, Chemistry, Geology/Earth Sciences, Astronomy.','atom','#3b82f6',0,1,'2026-02-16 00:22:25.315631',0);
INSERT INTO "subject" VALUES(5,'Biological Sciences','biological-sciences','Biology, Biochemistry, Microbiology, Genetics, Zoology','dna','#3b82f6',0,1,'2026-02-16 00:24:24.193223',0);
INSERT INTO "subject" VALUES(6,'Business Management','business-management','Business Administration, Human Resources, Operations.','business-time','#10b981',0,1,'2026-02-16 00:27:56.655167',0);
INSERT INTO "subject" VALUES(7,'Finance & Accounting','finance-accounting','Banking, Auditing, Financial Analysis.','file-invoice-dollar','#16a365',0,1,'2026-02-16 00:30:32.269790',0);
INSERT INTO "subject" VALUES(8,'Marketing','marketing','Digital Marketing, Advertising, Public Relations.','bullhorn','#16a465',0,1,'2026-02-16 00:32:03.264216',0);
INSERT INTO "subject" VALUES(9,'Economics','economics','Macroeconomics, Microeconomics, Econometrics.','chart-line','#15a366',0,1,'2026-02-16 00:34:34.272039',0);
INSERT INTO "subject" VALUES(10,'Medicine & Dentistry','medicine-dentistry','General Medicine, Surgery, Orthodontics.','stethoscope','#ed6437',0,1,'2026-02-16 00:35:42.851897',0);
INSERT INTO "subject" VALUES(11,'Nursing & Midwifery','nursing-midwifery','Clinical Nursing, Public Health Nursing','user-nurse','#ed6437',0,1,'2026-02-16 00:36:57.730479',0);
INSERT INTO "subject" VALUES(12,'Pharmacy','pharmacy','Pharmacology, Pharmaceutical Sciences.','capsules','#ee6438',0,1,'2026-02-16 00:38:40.161488',0);
INSERT INTO "subject" VALUES(13,'Allied Health','allied-health','Physiotherapy, Occupational Therapy, Radiography, Nutrition.','briefcase-medical','#ed6537',0,1,'2026-02-16 00:40:24.583860',0);
INSERT INTO "subject" VALUES(14,'Psychology','psychology','Clinical, Cognitive, Counseling, Forensic Psychology.','brain','#dc3558',0,1,'2026-02-16 00:41:06.185115',0);
INSERT INTO "subject" VALUES(15,'Sociology & Anthropology','sociology-anthropology','Social Work, Criminology, Cultural Studies.','comment','#dc3757',0,1,'2026-02-16 00:42:35.305945',0);
INSERT INTO "subject" VALUES(16,'Political Science','political-science','International Relations, Public Policy, Government.','landmark','#dc3857',0,1,'2026-02-16 00:43:38.347096',0);
INSERT INTO "subject" VALUES(17,'Geography','geography','Human Geography, GIS (Geographic Information Systems).','map','#dc3857',0,1,'2026-02-16 00:44:34.460163',0);
INSERT INTO "subject" VALUES(18,'History & Archaeology','history-archaeology','World History, Heritage Studies.','book','#7f4fa0',0,1,'2026-02-16 00:46:12.353658',0);
INSERT INTO "subject" VALUES(19,'Philosophy & Religion','philosophy-religion','Ethics, Theology, Logic.','hands-praying','#8150a1',0,1,'2026-02-16 00:48:01.186851',0);
INSERT INTO "subject" VALUES(20,'Languages & Literature','languages-literature','English, Linguistics, Modern Languages (French, Spanish, etc.)','language','#814fa0',0,1,'2026-02-16 00:50:17.076350',0);
INSERT INTO "subject" VALUES(21,'Fine Arts','fine-arts','Painting, Sculpture, Photography.','paintbrush','#814fa1',0,1,'2026-02-16 00:50:50.133745',0);
INSERT INTO "subject" VALUES(22,'Performing Arts','performing-arts','Music, Theatre/Drama, Dance.','masks-theater','#8250a1',0,1,'2026-02-16 00:52:33.214401',0);
INSERT INTO "subject" VALUES(23,'Law','law','Corporate Law, Criminal Law, International Law, Constitutional Law.','gavel','#8250a1',0,1,'2026-02-16 00:53:20.168377',0);
INSERT INTO "subject" VALUES(24,'Legal Studies','legal-studies','Paralegal Studies, Human Rights.','book','#814fa0',0,1,'2026-02-16 00:54:15.341432',0);
INSERT INTO "subject" VALUES(25,'Teacher Training','teacher-training','Early Childhood, Primary Education, Secondary Education.','school','#6ab1de',0,1,'2026-02-16 00:55:14.894541',0);
INSERT INTO "subject" VALUES(26,'Special Education','special-education','Learning Disabilities, Inclusive Education.','wheelchair-move','#6ab1de',0,1,'2026-02-16 00:56:09.272434',0);
INSERT INTO "subject" VALUES(27,'Educational Leadership','educational-leadership','School Management, Curriculum Design.','bullseye','#6bb0de',0,1,'2026-02-16 00:58:23.162077',0);
INSERT INTO "subject" VALUES(28,'Journalism','journalism','Print, Broadcast, Digital Media','newspaper','#da2184',0,1,'2026-02-16 00:59:32.784531',0);
INSERT INTO "subject" VALUES(29,'Communication Studies','communication-studies','Mass Communication, Media Theory.','comments','#da2184',0,1,'2026-02-16 01:00:25.844124',0);
INSERT INTO "subject" VALUES(30,'Film & Television','film-television','Production, Screenwriting, Cinematography.','film','#da2284',0,1,'2026-02-16 01:01:11.489827',0);
INSERT INTO "subject" VALUES(31,'Architecture','architecture','Urban Planning, Landscape Architecture.','bridge','#d6a443',0,1,'2026-02-16 01:02:27.704059',0);
INSERT INTO "subject" VALUES(32,'Design','design','Graphic Design, Fashion Design, Interior Design, Industrial Design.','pencil','#d5a442',0,1,'2026-02-16 01:03:42.708219',0);
INSERT INTO "subject" VALUES(33,'Construction','construction','Quantity Surveying, Real Estate Management.','hotel','#d5a342',0,1,'2026-02-16 01:04:49.400710',0);
INSERT INTO "subject" VALUES(34,'Agriculture','agriculture','Agronomy, Animal Science, Agribusiness.','seedling ','#1d8659',0,1,'2026-02-16 01:06:02.345625',0);
INSERT INTO "subject" VALUES(35,'Environmental Science','environmental-science','Ecology, Climate Change, Conservation','cloud-rain','#1d8559',0,1,'2026-02-16 01:07:10.653966',0);
INSERT INTO "subject" VALUES(36,'Veterinary Medicine','veterinary-medicine','Animal Health.','dog','#1d8559',0,1,'2026-02-16 01:07:58.848134',0);
CREATE TABLE user (
	id INTEGER NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(120), 
	bio TEXT, 
	profile_picture VARCHAR(200), 
	created_at DATETIME NOT NULL, 
	is_active BOOLEAN, 
	PRIMARY KEY (id)
);
INSERT INTO "user" VALUES(1,'Adwoa','alanfocus001@gmail.com','scrypt:32768:8:1$ZUhRtY45lekn6Hga$31f9cba2b3f6c46e01ef41ec184c874e1cfd2b78f5809a33852b5fb28fd9560d36bb578fd371c3e25d8c416ce73ec509d706a8ad36dfd4ed5f1d4a5e5fb0f80d','Adwoa Banehene',NULL,'default.jpg','2026-02-15 15:18:21.197000',1);
INSERT INTO "user" VALUES(2,'alan','attastudy7@gmail.com','scrypt:32768:8:1$ZIORkzjRqTEWy5re$0ea0700e398c54da37864d188fc456fb0390cd9a13e4d4df2bc47bce319185cf53966cf371d4d276026f5a837fc39175bb5a184433abe3297b9af23692d15799',' Kwabena Atta Twum','','acc71f919e19423c9f7a1a4de3f79466.jpg','2026-02-15 15:21:35.347482',1);
INSERT INTO "user" VALUES(3,'Kelvin','kelvin@gmail.com','scrypt:32768:8:1$1OmQDiFjw2sbWEuT$afaed6a49dfca346c4e7b245baf3eac49a3768b365e8b8cd1d1634805a339b120c1cee4d7817606bbe458567bd17ed7d7db0e981cf0c8cd1c083ee86eb61b065','Kelvin Asamoah',NULL,'default.jpg','2026-02-15 18:58:41.370964',1);
INSERT INTO "user" VALUES(4,'kantwum','jedidiah@gmail.com','scrypt:32768:8:1$5KexykJWo83LFuHP$caaed22bee9a14d642189c6952c001364fb96e1efd1373231bb1d3a002376b8b71fa505abc8eca0b4255ec1f06cfbe4360fb874ca9ac87b75845fede60236e72','Jedidiah Owusu',NULL,'default.jpg','2026-02-15 21:45:02.300722',1);
INSERT INTO "user" VALUES(5,'Muntari haidara','crmuntari@gmail.com','scrypt:32768:8:1$lhmDubZSHAbMKgMZ$1f135df182c6abedc7add9a3d53a7ea5eb6b394cc26c2828bb933537dd50e8aeb7744d45ecc759977dd24730aea21c2ee533a15020423b2b7447b35ee4f773b2','Muntari haidara',NULL,'default.jpg','2026-02-15 22:09:54.755264',1);
CREATE UNIQUE INDEX ix_user_email ON user (email);
CREATE UNIQUE INDEX ix_user_username ON user (username);
CREATE UNIQUE INDEX ix_subject_slug ON subject (slug);
CREATE UNIQUE INDEX ix_subject_name ON subject (name);
CREATE INDEX ix_post_created_at ON post (created_at);
CREATE INDEX ix_notification_created_at ON notification (created_at);
CREATE INDEX ix_comment_created_at ON comment (created_at);
COMMIT;
