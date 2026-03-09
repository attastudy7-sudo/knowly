"""
seed_subjects.py
Seeds all courses as Subject records, linked to their Programme.
Run from project root with venv active:
    python seed_subjects.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Programme, Subject

app = create_app()

# ---------------------------------------------------------------------------
# CSV data: (programme_name, year, semester, code, course_name)
# Where programme names exactly match seeded slugs.
# Duplicated programmes in the CSV: last block wins (deduped by course code).
# ---------------------------------------------------------------------------
COURSES_RAW = """BSc Business Administration,1,1,BA101,Principles of Management
BSc Business Administration,1,2,BA102,Business Communication
BSc Business Administration,2,1,BA201,Marketing Principles
BSc Business Administration,2,2,BA202,Human Resource Management
BSc Business Administration,3,1,BA301,Operations Management
BSc Business Administration,3,2,BA302,Strategic Management
BSc Business Administration,4,1,BA401,Entrepreneurship
BSc Business Administration,4,2,BA402,Business Strategy Project
BSc Accounting,1,1,AC101,Principles of Accounting
BSc Accounting,1,2,AC102,Financial Accounting
BSc Accounting,2,1,AC201,Cost Accounting
BSc Accounting,2,2,AC202,Taxation
BSc Accounting,3,1,AC301,Auditing
BSc Accounting,3,2,AC302,Corporate Finance
BSc Accounting,4,1,AC401,Advanced Financial Accounting
BSc Accounting,4,2,AC402,Accounting Research Project
BSc Marketing,1,1,MK101,Principles of Marketing
BSc Marketing,1,2,MK102,Consumer Behaviour
BSc Marketing,2,1,MK201,Marketing Research
BSc Marketing,2,2,MK202,Digital Marketing
BSc Marketing,3,1,MK301,Brand Management
BSc Marketing,3,2,MK302,Sales Management
BSc Marketing,4,1,MK401,Strategic Marketing
BSc Marketing,4,2,MK402,Marketing Project
BSc Human Resource Management,1,1,HR101,Introduction to HR
BSc Human Resource Management,1,2,HR102,Organizational Behavior
BSc Human Resource Management,2,1,HR201,Employee Relations
BSc Human Resource Management,2,2,HR202,Recruitment and Selection
BSc Human Resource Management,3,1,HR301,Training and Development
BSc Human Resource Management,3,2,HR302,Performance Management
BSc Human Resource Management,4,1,HR401,Compensation Management
BSc Human Resource Management,4,2,HR402,HR Project
BSc Banking and Finance,1,1,BF101,Principles of Banking
BSc Banking and Finance,1,2,BF102,Financial Accounting
BSc Banking and Finance,2,1,BF201,Corporate Finance
BSc Banking and Finance,2,2,BF202,Investment Analysis
BSc Banking and Finance,3,1,BF301,Risk Management
BSc Banking and Finance,3,2,BF302,Banking Operations
BSc Banking and Finance,4,1,BF401,Financial Markets
BSc Banking and Finance,4,2,BF402,Finance Project
BSc Supply Chain Management,1,1,SCM101,Introduction to Supply Chain
BSc Supply Chain Management,1,2,SCM102,Logistics Fundamentals
BSc Supply Chain Management,2,1,SCM201,Procurement Management
BSc Supply Chain Management,2,2,SCM202,Operations Management
BSc Supply Chain Management,3,1,SCM301,Inventory Management
BSc Supply Chain Management,3,2,SCM302,Supply Chain Analytics
BSc Supply Chain Management,4,1,SCM401,Strategic Supply Chain
BSc Supply Chain Management,4,2,SCM402,Supply Chain Project
BSc Entrepreneurship,1,1,ENP101,Principles of Entrepreneurship
BSc Entrepreneurship,1,2,ENP102,Business Idea Development
BSc Entrepreneurship,2,1,ENP201,Small Business Management
BSc Entrepreneurship,2,2,ENP202,Innovation Management
BSc Entrepreneurship,3,1,ENP301,Entrepreneurial Finance
BSc Entrepreneurship,3,2,ENP302,Marketing for Entrepreneurs
BSc Entrepreneurship,4,1,ENP401,Scaling Businesses
BSc Entrepreneurship,4,2,ENP402,Entrepreneurship Project
BA Economics,1,1,EC101,Microeconomics I
BA Economics,1,2,EC102,Macroeconomics I
BA Economics,2,1,EC201,Intermediate Microeconomics
BA Economics,2,2,EC202,Intermediate Macroeconomics
BA Economics,3,1,EC301,Econometrics
BA Economics,3,2,EC302,Development Economics
BA Economics,4,1,EC401,International Economics
BA Economics,4,2,EC402,Economics Research Project
BA Political Science,1,1,PS101,Introduction to Political Science
BA Political Science,1,2,PS102,African Politics
BA Political Science,2,1,PS201,Comparative Politics
BA Political Science,2,2,PS202,Public Administration
BA Political Science,3,1,PS301,International Relations
BA Political Science,3,2,PS302,Political Theory
BA Political Science,4,1,PS401,Public Policy Analysis
BA Political Science,4,2,PS402,Political Science Thesis
BA Sociology,1,1,SO101,Introduction to Sociology
BA Sociology,1,2,SO102,Social Problems
BA Sociology,2,1,SO201,Social Theory
BA Sociology,2,2,SO202,Urban Sociology
BA Sociology,3,1,SO301,Gender Studies
BA Sociology,3,2,SO302,Research Methods
BA Sociology,4,1,SO401,Development Sociology
BA Sociology,4,2,SO402,Sociology Project
BA Psychology,1,1,PY101,Introduction to Psychology
BA Psychology,1,2,PY102,Developmental Psychology
BA Psychology,2,1,PY201,Cognitive Psychology
BA Psychology,2,2,PY202,Abnormal Psychology
BA Psychology,3,1,PY301,Social Psychology
BA Psychology,3,2,PY302,Research Methods in Psychology
BA Psychology,4,1,PY401,Clinical Psychology
BA Psychology,4,2,PY402,Psychology Thesis
BA Communication Studies,1,1,CM101,Introduction to Communication
BA Communication Studies,1,2,CM102,Media Writing
BA Communication Studies,2,1,CM201,Journalism Principles
BA Communication Studies,2,2,CM202,Public Relations
BA Communication Studies,3,1,CM301,Broadcast Journalism
BA Communication Studies,3,2,CM302,Media Ethics
BA Communication Studies,4,1,CM401,Strategic Communication
BA Communication Studies,4,2,CM402,Communication Research Project
BA History,1,1,HI101,Introduction to World History
BA History,1,2,HI102,African History
BA History,2,1,HI201,History of Ghana
BA History,2,2,HI202,Colonial Africa
BA History,3,1,HI301,Modern African History
BA History,3,2,HI302,Historical Research Methods
BA History,4,1,HI401,Global History
BA History,4,2,HI402,History Thesis
BA English,1,1,EN101,Introduction to Literature
BA English,1,2,EN102,Academic Writing
BA English,2,1,EN201,African Literature
BA English,2,2,EN202,Literary Theory
BA English,3,1,EN301,Postcolonial Literature
BA English,3,2,EN302,Creative Writing
BA English,4,1,EN401,Advanced Literary Studies
BA English,4,2,EN402,English Thesis
BA Philosophy,1,1,PHL101,Introduction to Philosophy
BA Philosophy,1,2,PHL102,Ethics
BA Philosophy,2,1,PHL201,Logic
BA Philosophy,2,2,PHL202,Political Philosophy
BA Philosophy,3,1,PHL301,Philosophy of Mind
BA Philosophy,3,2,PHL302,Philosophy of Science
BA Philosophy,4,1,PHL401,Contemporary Philosophy
BA Philosophy,4,2,PHL402,Philosophy Thesis
BA Linguistics,1,1,LG101,Introduction to Linguistics
BA Linguistics,1,2,LG102,Phonetics
BA Linguistics,2,1,LG201,Phonology
BA Linguistics,2,2,LG202,Syntax
BA Linguistics,3,1,LG301,Sociolinguistics
BA Linguistics,3,2,LG302,Language Acquisition
BA Linguistics,4,1,LG401,Applied Linguistics
BA Linguistics,4,2,LG402,Linguistics Thesis
BSc Computer Science,1,1,CS101,Introduction to Programming
BSc Computer Science,1,2,CS102,Discrete Mathematics
BSc Computer Science,1,3,CS103,Computer Systems Fundamentals
BSc Computer Science,2,1,CS201,Data Structures and Algorithms
BSc Computer Science,2,2,CS202,Operating Systems
BSc Computer Science,2,3,CS203,Database Systems
BSc Computer Science,3,1,CS301,Artificial Intelligence
BSc Computer Science,3,2,CS302,Computer Networks
BSc Computer Science,4,1,CS401,Machine Learning
BSc Computer Science,4,2,CS402,Final Year Project
BSc Information Technology,1,1,IT101,Introduction to IT
BSc Information Technology,1,2,IT102,Computer Fundamentals
BSc Information Technology,2,1,IT201,Networking Essentials
BSc Information Technology,2,2,IT202,Web Development
BSc Information Technology,3,1,IT301,Cloud Computing
BSc Information Technology,3,2,IT302,Cybersecurity Fundamentals
BSc Information Technology,4,1,IT401,IT Project Management
BSc Information Technology,4,2,IT402,IT Capstone Project
BSc Software Engineering,1,1,SE101,Introduction to Software Engineering
BSc Software Engineering,1,2,SE102,Programming Fundamentals
BSc Software Engineering,2,1,SE201,Object-Oriented Programming
BSc Software Engineering,2,2,SE202,Database Systems
BSc Software Engineering,3,1,SE301,Software Project Management
BSc Software Engineering,3,2,SE302,Software Quality Assurance
BSc Software Engineering,4,1,SE401,Agile Methodologies
BSc Software Engineering,4,2,SE402,Capstone Project
BSc Data Science,1,1,DS101,Introduction to Data Science
BSc Data Science,1,2,DS102,Statistics for Data Science
BSc Data Science,2,1,DS201,Machine Learning I
BSc Data Science,2,2,DS202,Database Systems
BSc Data Science,3,1,DS301,Data Mining
BSc Data Science,3,2,DS302,Big Data Analytics
BSc Data Science,4,1,DS401,AI and Deep Learning
BSc Data Science,4,2,DS402,Data Science Project
BSc Artificial Intelligence,1,1,AI101,Introduction to AI
BSc Artificial Intelligence,1,2,AI102,Programming for AI
BSc Artificial Intelligence,2,1,AI201,Machine Learning
BSc Artificial Intelligence,2,2,AI202,Data Structures for AI
BSc Artificial Intelligence,3,1,AI301,Computer Vision
BSc Artificial Intelligence,3,2,AI302,Natural Language Processing
BSc Artificial Intelligence,4,1,AI401,AI Ethics and Policy
BSc Artificial Intelligence,4,2,AI402,AI Project
BSc Cybersecurity,1,1,CSY101,Introduction to Cybersecurity
BSc Cybersecurity,1,2,CSY102,Network Security
BSc Cybersecurity,2,1,CSY201,Cryptography
BSc Cybersecurity,2,2,CSY202,Ethical Hacking
BSc Cybersecurity,3,1,CSY301,Security Policy & Management
BSc Cybersecurity,3,2,CSY302,Penetration Testing
BSc Cybersecurity,4,1,CSY401,Cybersecurity Project I
BSc Cybersecurity,4,2,CSY402,Cybersecurity Project II
BSc Electrical & Electronic Engineering,1,1,EEE101,Circuit Theory
BSc Electrical & Electronic Engineering,1,2,EEE102,Electronics I
BSc Electrical & Electronic Engineering,2,1,EEE201,Signals and Systems
BSc Electrical & Electronic Engineering,2,2,EEE202,Digital Electronics
BSc Electrical & Electronic Engineering,3,1,EEE301,Control Systems
BSc Electrical & Electronic Engineering,3,2,EEE302,Power Systems
BSc Electrical & Electronic Engineering,4,1,EEE401,Electrical Project Management
BSc Electrical & Electronic Engineering,4,2,EEE402,Electrical Engineering Project
BSc Mechanical Engineering,1,1,ME101,Thermodynamics I
BSc Mechanical Engineering,1,2,ME102,Engineering Drawing
BSc Mechanical Engineering,2,1,ME201,Mechanics of Materials
BSc Mechanical Engineering,2,2,ME202,Fluid Mechanics
BSc Mechanical Engineering,3,1,ME301,Heat Transfer
BSc Mechanical Engineering,3,2,ME302,Manufacturing Processes
BSc Mechanical Engineering,4,1,ME401,Project Management
BSc Mechanical Engineering,4,2,ME402,Mechanical Engineering Project
BSc Civil Engineering,1,1,CE101,Engineering Mechanics
BSc Civil Engineering,1,2,CE102,Statics and Dynamics
BSc Civil Engineering,2,1,CE201,Structural Analysis
BSc Civil Engineering,2,2,CE202,Fluid Mechanics
BSc Civil Engineering,3,1,CE301,Geotechnical Engineering
BSc Civil Engineering,3,2,CE302,Transportation Engineering
BSc Civil Engineering,4,1,CE401,Construction Management
BSc Civil Engineering,4,2,CE402,Civil Engineering Project
BSc Petroleum Engineering,1,1,PE101,Introduction to Petroleum Engineering
BSc Petroleum Engineering,1,2,PE102,Engineering Mathematics
BSc Petroleum Engineering,2,1,PE201,Reservoir Engineering I
BSc Petroleum Engineering,2,2,PE202,Fluid Mechanics
BSc Petroleum Engineering,3,1,PE301,Drilling Engineering
BSc Petroleum Engineering,3,2,PE302,Production Engineering
BSc Petroleum Engineering,4,1,PE401,Petroleum Project Management
BSc Petroleum Engineering,4,2,PE402,Petroleum Engineering Project
BSc Architecture,1,1,AR101,Introduction to Architecture
BSc Architecture,1,2,AR102,Design Fundamentals
BSc Architecture,2,1,AR201,Building Technology
BSc Architecture,2,2,AR202,Construction Materials
BSc Architecture,3,1,AR301,Architectural Design III
BSc Architecture,3,2,AR302,Urban Architecture
BSc Architecture,4,1,AR401,Professional Practice
BSc Architecture,4,2,AR402,Architecture Thesis
BSc Urban and Regional Planning,1,1,URP101,Introduction to Urban Planning
BSc Urban and Regional Planning,1,2,URP102,Cartography and GIS
BSc Urban and Regional Planning,2,1,URP201,Urban Design
BSc Urban and Regional Planning,2,2,URP202,Land Use Planning
BSc Urban and Regional Planning,3,1,URP301,Transportation Planning
BSc Urban and Regional Planning,3,2,URP302,Environmental Planning
BSc Urban and Regional Planning,4,1,URP401,Urban Policy and Governance
BSc Urban and Regional Planning,4,2,URP402,Planning Project
BSc Mathematics,1,1,MA101,Calculus I
BSc Mathematics,1,2,MA102,Linear Algebra
BSc Mathematics,2,1,MA201,Calculus II
BSc Mathematics,2,2,MA202,Differential Equations
BSc Mathematics,3,1,MA301,Probability and Statistics
BSc Mathematics,3,2,MA302,Abstract Algebra
BSc Mathematics,4,1,MA401,Real Analysis
BSc Mathematics,4,2,MA402,Mathematics Project
BSc Statistics,1,1,ST101,Introduction to Statistics
BSc Statistics,1,2,ST102,Probability Theory
BSc Statistics,2,1,ST201,Regression Analysis
BSc Statistics,2,2,ST202,Multivariate Statistics
BSc Statistics,3,1,ST301,Time Series Analysis
BSc Statistics,3,2,ST302,Statistical Computing
BSc Statistics,4,1,ST401,Advanced Statistical Methods
BSc Statistics,4,2,ST402,Statistics Project
BSc Physics,1,1,PHYS101,Classical Mechanics
BSc Physics,1,2,PHYS102,Electricity and Magnetism
BSc Physics,2,1,PHYS201,Quantum Mechanics
BSc Physics,2,2,PHYS202,Thermodynamics
BSc Physics,3,1,PHYS301,Solid State Physics
BSc Physics,3,2,PHYS302,Nuclear Physics
BSc Physics,4,1,PHYS401,Particle Physics
BSc Physics,4,2,PHYS402,Physics Research Project
BSc Chemistry,1,1,CH101,General Chemistry
BSc Chemistry,1,2,CH102,Organic Chemistry I
BSc Chemistry,2,1,CH201,Inorganic Chemistry
BSc Chemistry,2,2,CH202,Physical Chemistry
BSc Chemistry,3,1,CH301,Analytical Chemistry
BSc Chemistry,3,2,CH302,Biochemistry
BSc Chemistry,4,1,CH401,Industrial Chemistry
BSc Chemistry,4,2,CH402,Chemistry Project
BSc Biology,1,1,BI101,General Biology
BSc Biology,1,2,BI102,Cell Biology
BSc Biology,2,1,BI201,Genetics
BSc Biology,2,2,BI202,Microbiology
BSc Biology,3,1,BI301,Ecology
BSc Biology,3,2,BI302,Plant Physiology
BSc Biology,4,1,BI401,Molecular Biology
BSc Biology,4,2,BI402,Biology Research Project
BSc Environmental Science,1,1,ES101,Introduction to Environmental Science
BSc Environmental Science,1,2,ES102,Ecosystem Dynamics
BSc Environmental Science,2,1,ES201,Environmental Chemistry
BSc Environmental Science,2,2,ES202,Environmental Microbiology
BSc Environmental Science,3,1,ES301,Climate Change Science
BSc Environmental Science,3,2,ES302,Pollution Control
BSc Environmental Science,4,1,ES401,Environmental Impact Assessment
BSc Environmental Science,4,2,ES402,Environmental Project
BSc Agriculture,1,1,AG101,Introduction to Agriculture
BSc Agriculture,1,2,AG102,Crop Science
BSc Agriculture,2,1,AG201,Soil Science
BSc Agriculture,2,2,AG202,Animal Science
BSc Agriculture,3,1,AG301,Agroforestry
BSc Agriculture,3,2,AG302,Agri-Business Management
BSc Agriculture,4,1,AG401,Agricultural Research Methods
BSc Agriculture,4,2,AG402,Agriculture Project
BSc Agribusiness,1,1,AB101,Principles of Agribusiness
BSc Agribusiness,1,2,AB102,Agricultural Marketing
BSc Agribusiness,2,1,AB201,Farm Management
BSc Agribusiness,2,2,AB202,Agricultural Finance
BSc Agribusiness,3,1,AB301,Supply Chain in Agriculture
BSc Agribusiness,3,2,AB302,Agribusiness Strategy
BSc Agribusiness,4,1,AB401,Agribusiness Policy
BSc Agribusiness,4,2,AB402,Agribusiness Project
BSc Soil Science,1,1,SS101,Introduction to Soil Science
BSc Soil Science,1,2,SS102,Soil Chemistry
BSc Soil Science,2,1,SS201,Soil Physics
BSc Soil Science,2,2,SS202,Soil Fertility Management
BSc Soil Science,3,1,SS301,Soil and Water Conservation
BSc Soil Science,3,2,SS302,Land Use Planning
BSc Soil Science,4,1,SS401,Research Methods
BSc Soil Science,4,2,SS402,Soil Science Project
BSc Fisheries,1,1,FSH101,Introduction to Fisheries
BSc Fisheries,1,2,FSH102,Aquatic Biology
BSc Fisheries,2,1,FSH201,Fish Breeding
BSc Fisheries,2,2,FSH202,Fish Nutrition
BSc Fisheries,3,1,FSH301,Fisheries Management
BSc Fisheries,3,2,FSH302,Aquaculture
BSc Fisheries,4,1,FSH401,Fisheries Research Methods
BSc Fisheries,4,2,FSH402,Fisheries Project
BSc Veterinary Medicine,1,1,VM101,Introduction to Veterinary Science
BSc Veterinary Medicine,1,2,VM102,Animal Anatomy
BSc Veterinary Medicine,2,1,VM201,Animal Physiology
BSc Veterinary Medicine,2,2,VM202,Animal Nutrition
BSc Veterinary Medicine,3,1,VM301,Pathology
BSc Veterinary Medicine,3,2,VM302,Clinical Veterinary Practice
BSc Veterinary Medicine,4,1,VM401,Veterinary Pharmacology
BSc Veterinary Medicine,4,2,VM402,Veterinary Project
BSc Nursing,1,1,NS101,Anatomy and Physiology I
BSc Nursing,1,2,NS102,Basic Nursing Skills
BSc Nursing,2,1,NS201,Medical-Surgical Nursing I
BSc Nursing,2,2,NS202,Pharmacology for Nursing
BSc Nursing,3,1,NS301,Medical-Surgical Nursing II
BSc Nursing,3,2,NS302,Mental Health Nursing
BSc Nursing,4,1,NS401,Community Health Nursing
BSc Nursing,4,2,NS402,Nursing Research Project
BSc Public Health,1,1,PH101,Introduction to Public Health
BSc Public Health,1,2,PH102,Epidemiology I
BSc Public Health,2,1,PH201,Biostatistics
BSc Public Health,2,2,PH202,Health Promotion
BSc Public Health,3,1,PH301,Environmental Health
BSc Public Health,3,2,PH302,Global Health
BSc Public Health,4,1,PH401,Health Policy
BSc Public Health,4,2,PH402,Public Health Project
BSc Midwifery,1,1,MW101,Anatomy and Physiology for Midwifery
BSc Midwifery,1,2,MW102,Fundamentals of Midwifery
BSc Midwifery,2,1,MW201,Obstetrics I
BSc Midwifery,2,2,MW202,Community Midwifery
BSc Midwifery,3,1,MW301,Obstetrics II
BSc Midwifery,3,2,MW302,Neonatal Care
BSc Midwifery,4,1,MW401,Advanced Midwifery
BSc Midwifery,4,2,MW402,Midwifery Project
BSc Nutrition and Dietetics,1,1,ND101,Human Nutrition
BSc Nutrition and Dietetics,1,2,ND102,Food Composition
BSc Nutrition and Dietetics,2,1,ND201,Nutritional Biochemistry
BSc Nutrition and Dietetics,2,2,ND202,Dietetics
BSc Nutrition and Dietetics,3,1,ND301,Public Health Nutrition
BSc Nutrition and Dietetics,3,2,ND302,Clinical Nutrition
BSc Nutrition and Dietetics,4,1,ND401,Nutrition Policy
BSc Nutrition and Dietetics,4,2,ND402,Nutrition Project
BSc Pharmacy,1,1,PHM101,Pharmaceutical Chemistry I
BSc Pharmacy,1,2,PHM102,Biochemistry for Pharmacy
BSc Pharmacy,2,1,PHM201,Pharmacology I
BSc Pharmacy,2,2,PHM202,Pharmaceutics I
BSc Pharmacy,3,1,PHM301,Pharmacology II
BSc Pharmacy,3,2,PHM302,Pharmaceutics II
BSc Pharmacy,4,1,PHM401,Clinical Pharmacy
BSc Pharmacy,4,2,PHM402,Pharmacy Project
BSc Physiotherapy,1,1,PT101,Human Anatomy
BSc Physiotherapy,1,2,PT102,Physiology
BSc Physiotherapy,2,1,PT201,Kinesiology
BSc Physiotherapy,2,2,PT202,Exercise Therapy
BSc Physiotherapy,3,1,PT301,Neurological Physiotherapy
BSc Physiotherapy,3,2,PT302,Cardiopulmonary Physiotherapy
BSc Physiotherapy,4,1,PT401,Clinical Practice I
BSc Physiotherapy,4,2,PT402,Clinical Practice II
BSc Radiography,1,1,RD101,Anatomy and Physiology
BSc Radiography,1,2,RD102,Medical Imaging Fundamentals
BSc Radiography,2,1,RD201,Diagnostic Radiography I
BSc Radiography,2,2,RD202,Diagnostic Radiography II
BSc Radiography,3,1,RD301,Medical Physics
BSc Radiography,3,2,RD302,Radiation Safety
BSc Radiography,4,1,RD401,Advanced Imaging Techniques
BSc Radiography,4,2,RD402,Radiography Project
BSc Occupational Therapy,1,1,OT101,Introduction to Occupational Therapy
BSc Occupational Therapy,1,2,OT102,Human Anatomy
BSc Occupational Therapy,2,1,OT201,Physiology for OT
BSc Occupational Therapy,2,2,OT202,Activity Analysis
BSc Occupational Therapy,3,1,OT301,Pediatric OT
BSc Occupational Therapy,3,2,OT302,Neurological OT
BSc Occupational Therapy,4,1,OT401,Clinical Practice I
BSc Occupational Therapy,4,2,OT402,Occupational Therapy Project
BSc Speech and Language Therapy,1,1,SL101,Introduction to Speech Therapy
BSc Speech and Language Therapy,1,2,SL102,Human Anatomy and Physiology
BSc Speech and Language Therapy,2,1,SL201,Phonetics and Phonology
BSc Speech and Language Therapy,2,2,SL202,Language Development
BSc Speech and Language Therapy,3,1,SL301,Clinical Speech Therapy I
BSc Speech and Language Therapy,3,2,SL302,Clinical Speech Therapy II
BSc Speech and Language Therapy,4,1,SL401,Advanced Speech Therapy
BSc Speech and Language Therapy,4,2,SL402,Speech Therapy Project
BSc Fine Arts,1,1,FA101,Drawing and Painting I
BSc Fine Arts,1,2,FA102,Sculpture I
BSc Fine Arts,2,1,FA201,Drawing and Painting II
BSc Fine Arts,2,2,FA202,Sculpture II
BSc Fine Arts,3,1,FA301,Printmaking
BSc Fine Arts,3,2,FA302,Art History
BSc Fine Arts,4,1,FA401,Studio Practice
BSc Fine Arts,4,2,FA402,Final Art Project
BSc Theatre Arts,1,1,TA101,Introduction to Theatre
BSc Theatre Arts,1,2,TA102,Stagecraft
BSc Theatre Arts,2,1,TA201,Acting I
BSc Theatre Arts,2,2,TA202,Directing I
BSc Theatre Arts,3,1,TA301,Acting II
BSc Theatre Arts,3,2,TA302,Directing II
BSc Theatre Arts,4,1,TA401,Theatre Production
BSc Theatre Arts,4,2,TA402,Theatre Project
BSc Music,1,1,MU101,Music Theory I
BSc Music,1,2,MU102,Introduction to Music
BSc Music,2,1,MU201,Music History
BSc Music,2,2,MU202,Instrumental Practice
BSc Music,3,1,MU301,Composition
BSc Music,3,2,MU302,Conducting
BSc Music,4,1,MU401,Music Research
BSc Music,4,2,MU402,Music Project
BSc Fashion & Textile Design,1,1,FTD101,Introduction to Fashion
BSc Fashion & Textile Design,1,2,FTD102,Textile Technology
BSc Fashion & Textile Design,2,1,FTD201,Garment Construction
BSc Fashion & Textile Design,2,2,FTD202,Fashion Illustration
BSc Fashion & Textile Design,3,1,FTD301,Fashion Marketing
BSc Fashion & Textile Design,3,2,FTD302,Creative Fashion Design
BSc Fashion & Textile Design,4,1,FTD401,Fashion Project I
BSc Fashion & Textile Design,4,2,FTD402,Fashion Project II
BSc Hospitality & Tourism Management,1,1,HTM101,Introduction to Hospitality
BSc Hospitality & Tourism Management,1,2,HTM102,Food and Beverage Operations
BSc Hospitality & Tourism Management,2,1,HTM201,Lodging Management
BSc Hospitality & Tourism Management,2,2,HTM202,Event Planning
BSc Hospitality & Tourism Management,3,1,HTM301,Tourism Marketing
BSc Hospitality & Tourism Management,3,2,HTM302,Sustainable Hospitality
BSc Hospitality & Tourism Management,4,1,HTM401,Hospitality Research
BSc Hospitality & Tourism Management,4,2,HTM402,Hospitality Project
BSc Hotel and Catering Management,1,1,HCM101,Introduction to Hotel Management
BSc Hotel and Catering Management,1,2,HCM102,Food Production I
BSc Hotel and Catering Management,2,1,HCM201,Food Production II
BSc Hotel and Catering Management,2,2,HCM202,Front Office Operations
BSc Hotel and Catering Management,3,1,HCM301,Event Management
BSc Hotel and Catering Management,3,2,HCM302,Hospitality Marketing
BSc Hotel and Catering Management,4,1,HCM401,Hospitality Research
BSc Hotel and Catering Management,4,2,HCM402,Hotel Project
BSc Tourism and Events Management,1,1,TE101,Introduction to Tourism
BSc Tourism and Events Management,1,2,TE102,Event Management Basics
BSc Tourism and Events Management,2,1,TE201,Destination Management
BSc Tourism and Events Management,2,2,TE202,Hospitality Operations
BSc Tourism and Events Management,3,1,TE301,Sustainable Tourism
BSc Tourism and Events Management,3,2,TE302,Event Marketing
BSc Tourism and Events Management,4,1,TE401,Strategic Event Management
BSc Tourism and Events Management,4,2,TE402,Tourism Project
LLB Law,1,1,LAW101,Introduction to Law
LLB Law,1,2,LAW102,Constitutional Law I
LLB Law,2,1,LAW201,Criminal Law
LLB Law,2,2,LAW202,Contract Law
LLB Law,3,1,LAW301,Property Law
LLB Law,3,2,LAW302,Equity and Trusts
LLB Law,4,1,LAW401,Commercial Law
LLB Law,4,2,LAW402,Law Dissertation
BSc Criminology and Security Studies,1,1,CSE101,Introduction to Criminology
BSc Criminology and Security Studies,1,2,CSE102,Security Studies
BSc Criminology and Security Studies,2,1,CSE201,Crime Analysis
BSc Criminology and Security Studies,2,2,CSE202,Criminal Law
BSc Criminology and Security Studies,3,1,CSE301,Forensic Science
BSc Criminology and Security Studies,3,2,CSE302,Counterterrorism
BSc Criminology and Security Studies,4,1,CSE401,Research Methods
BSc Criminology and Security Studies,4,2,CSE402,Security Project
BSc Education (Mathematics),1,1,EDM101,Foundations of Education
BSc Education (Mathematics),1,2,EDM102,Mathematics I
BSc Education (Mathematics),2,1,EDM201,Mathematics II
BSc Education (Mathematics),2,2,EDM202,Educational Psychology
BSc Education (Mathematics),3,1,EDM301,Teaching Methods in Mathematics
BSc Education (Mathematics),3,2,EDM302,Mathematics Curriculum Development
BSc Education (Mathematics),4,1,EDM401,Teaching Practicum I
BSc Education (Mathematics),4,2,EDM402,Teaching Practicum II
BSc Education (Science),1,1,EDS101,Foundations of Education
BSc Education (Science),1,2,EDS102,General Science I
BSc Education (Science),2,1,EDS201,General Science II
BSc Education (Science),2,2,EDS202,Educational Psychology
BSc Education (Science),3,1,EDS301,Teaching Methods in Science
BSc Education (Science),3,2,EDS302,Science Curriculum Development
BSc Education (Science),4,1,EDS401,Teaching Practicum I
BSc Education (Science),4,2,EDS402,Teaching Practicum II"""

# Programme name → colour (matches seed_programmes.py)
PROGRAMME_COLORS = {
    "BSc Business Administration": "#f59e0b", "BSc Accounting": "#f59e0b",
    "BSc Marketing": "#f59e0b", "BSc Human Resource Management": "#f59e0b",
    "BSc Banking and Finance": "#f59e0b", "BSc Supply Chain Management": "#f59e0b",
    "BSc Entrepreneurship": "#f59e0b",
    "BA Economics": "#8b5cf6", "BA Political Science": "#8b5cf6",
    "BA Sociology": "#8b5cf6", "BA Psychology": "#8b5cf6",
    "BA Communication Studies": "#8b5cf6", "BA History": "#8b5cf6",
    "BA English": "#8b5cf6", "BA Philosophy": "#8b5cf6", "BA Linguistics": "#8b5cf6",
    "BSc Computer Science": "#2563eb", "BSc Information Technology": "#2563eb",
    "BSc Software Engineering": "#2563eb", "BSc Data Science": "#2563eb",
    "BSc Artificial Intelligence": "#2563eb", "BSc Cybersecurity": "#2563eb",
    "BSc Electrical & Electronic Engineering": "#64748b", "BSc Mechanical Engineering": "#64748b",
    "BSc Civil Engineering": "#64748b", "BSc Petroleum Engineering": "#64748b",
    "BSc Architecture": "#64748b", "BSc Urban and Regional Planning": "#64748b",
    "BSc Mathematics": "#06b6d4", "BSc Statistics": "#06b6d4",
    "BSc Physics": "#06b6d4", "BSc Chemistry": "#06b6d4",
    "BSc Biology": "#06b6d4", "BSc Environmental Science": "#06b6d4",
    "BSc Agriculture": "#16a34a", "BSc Agribusiness": "#16a34a",
    "BSc Soil Science": "#16a34a", "BSc Fisheries": "#16a34a",
    "BSc Veterinary Medicine": "#16a34a",
    "BSc Nursing": "#ef4444", "BSc Public Health": "#ef4444",
    "BSc Midwifery": "#ef4444", "BSc Nutrition and Dietetics": "#ef4444",
    "BSc Pharmacy": "#ef4444", "BSc Physiotherapy": "#ef4444",
    "BSc Radiography": "#ef4444", "BSc Occupational Therapy": "#ef4444",
    "BSc Speech and Language Therapy": "#ef4444",
    "BSc Fine Arts": "#ec4899", "BSc Theatre Arts": "#ec4899",
    "BSc Music": "#ec4899", "BSc Fashion & Textile Design": "#ec4899",
    "BSc Hospitality & Tourism Management": "#ec4899",
    "BSc Hotel and Catering Management": "#ec4899",
    "BSc Tourism and Events Management": "#ec4899",
    "LLB Law": "#92400e", "BSc Criminology and Security Studies": "#92400e",
    "BSc Education (Mathematics)": "#0891b2", "BSc Education (Science)": "#0891b2",
}

# Course code → icon mapping (sensible defaults by discipline prefix)
def icon_for_code(code, course_name):
    prefix = ''.join(c for c in code if c.isalpha()).upper()
    icons = {
        "CS": "laptop-code", "IT": "server", "SE": "code", "DS": "chart-bar",
        "AI": "robot", "CSY": "shield-halved",
        "EEE": "bolt", "ME": "gear", "CE": "building",
        "PE": "oil-well", "AR": "drafting-compass", "URP": "map",
        "MA": "square-root-variable", "ST": "chart-simple", "PHYS": "atom",
        "CH": "flask", "BI": "dna", "ES": "leaf",
        "AG": "tractor", "AB": "store", "SS": "hill-rockslide",
        "FSH": "fish", "VM": "paw",
        "NS": "user-nurse", "PH": "heart-pulse", "MW": "baby",
        "ND": "apple-whole", "PHM": "pills", "PT": "person-walking",
        "RD": "x-ray", "OT": "hand-holding-heart", "SL": "microphone",
        "FA": "palette", "TA": "masks-theater", "MU": "music",
        "FTD": "scissors", "HTM": "concierge-bell", "HCM": "utensils",
        "TE": "map-location-dot",
        "LAW": "scale-balanced", "CSE": "shield",
        "EDM": "chalkboard-user", "EDS": "chalkboard-user",
        "BA": "briefcase", "AC": "calculator", "MK": "bullhorn",
        "HR": "users", "BF": "landmark", "SCM": "truck", "ENP": "lightbulb",
        "EC": "chart-line", "PS": "landmark-flag", "SO": "people-group",
        "PY": "brain", "CM": "comments", "HI": "scroll",
        "EN": "book-open", "PHL": "infinity", "LG": "language",
    }
    # Try longest prefix match first
    for length in range(len(prefix), 0, -1):
        if prefix[:length] in icons:
            return icons[prefix[:length]]
    return "book"


def make_slug(code):
    return code.lower().replace(" ", "-")


def seed():
    with app.app_context():
        # Build programme lookup: name → Programme object
        all_programmes = {p.name: p for p in Programme.query.all()}

        added = skipped = unmatched = 0
        seen_codes = set()

        for line in COURSES_RAW.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # Split on comma but max 5 parts (course name may not have commas here)
            parts = line.split(",", 4)
            if len(parts) < 5:
                continue
            prog_name, year, semester, code, course_name = (p.strip() for p in parts)

            # Skip duplicates by course code
            if code in seen_codes:
                continue
            seen_codes.add(code)

            # Match to seeded programme
            programme = all_programmes.get(prog_name)
            if not programme:
                print(f"  SKIP (no programme match): {prog_name} — {code}")
                unmatched += 1
                continue

            slug = make_slug(code)

            # Skip if subject with this slug already exists
            if Subject.query.filter_by(slug=slug).first():
                skipped += 1
                continue

            order = (int(year) - 1) * 20 + (int(semester) - 1) * 10
            color = PROGRAMME_COLORS.get(prog_name, "#6366f1")
            icon  = icon_for_code(code, course_name)

            db.session.add(Subject(
                name=f"{code} – {course_name}",
                slug=slug,
                icon=icon,
                color=color,
                order=order,
                is_active=True,
                programme_id=programme.id,
            ))
            added += 1

        db.session.commit()
        print(f"\n✓ Done — {added} subjects added, {skipped} already existed, {unmatched} unmatched programmes skipped.")


if __name__ == "__main__":
    seed()