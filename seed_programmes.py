"""
Seed script: inserts Programmes, Subjects, and Faculty mappings into Neon DB.
Run from the knowly/ directory:
    python seed_programmes.py
"""

import os, re, csv, io
from dotenv import load_dotenv

load_dotenv()

# ── Inline data ───────────────────────────────────────────────────────────────

FACULTY_MAP = {
    # Business & Management
    "BSc Business Administration":          "Business & Management",
    "BSc Accounting":                        "Business & Management",
    "BSc Marketing":                         "Business & Management",
    "BSc Human Resource Management":        "Business & Management",
    "BSc Banking and Finance":              "Business & Management",
    "BSc Supply Chain Management":          "Business & Management",
    "BSc Entrepreneurship":                 "Business & Management",
    "BSc Finance":                           "Business & Management",
    "BSc Logistics and Supply Chain Management": "Business & Management",
    "BSc Logistics & Transport Management": "Business & Management",
    "BSc International Business":           "Business & Management",
    "BSc Agribusiness":                     "Business & Management",

    # Social Sciences & Humanities
    "BA Economics":                          "Social Sciences & Humanities",
    "BSc Economics":                         "Social Sciences & Humanities",
    "BA Political Science":                  "Social Sciences & Humanities",
    "BSc Political Science":                 "Social Sciences & Humanities",
    "BA Sociology":                          "Social Sciences & Humanities",
    "BSc Sociology":                         "Social Sciences & Humanities",
    "BA Psychology":                         "Social Sciences & Humanities",
    "BSc Psychology":                        "Social Sciences & Humanities",
    "BA Communication Studies":             "Social Sciences & Humanities",
    "BA History":                            "Social Sciences & Humanities",
    "BA English":                            "Social Sciences & Humanities",
    "BA Philosophy":                         "Social Sciences & Humanities",
    "BA Linguistics":                        "Social Sciences & Humanities",
    "BSc Social Work":                       "Social Sciences & Humanities",
    "BSc Public Administration":            "Social Sciences & Humanities",
    "BSc Journalism":                        "Social Sciences & Humanities",
    "BSc Library and Information Science":  "Social Sciences & Humanities",
    "BSc Criminology":                       "Social Sciences & Humanities",
    "BSc Criminology and Security Studies": "Social Sciences & Humanities",

    # Computing & Technology
    "BSc Computer Science":                 "Computing & Technology",
    "BSc Information Technology":           "Computing & Technology",
    "BSc Software Engineering":             "Computing & Technology",
    "BSc Data Science":                     "Computing & Technology",
    "BSc Data Analytics":                   "Computing & Technology",
    "BSc Artificial Intelligence":          "Computing & Technology",
    "BSc Cybersecurity":                    "Computing & Technology",
    "BSc Information Systems":              "Computing & Technology",
    "BSc Artificial Life Sciences":         "Computing & Technology",

    # Engineering
    "BSc Electrical Engineering":           "Engineering",
    "BSc Electrical & Electronic Engineering": "Engineering",
    "BSc Mechanical Engineering":           "Engineering",
    "BSc Civil Engineering":                "Engineering",
    "BSc Petroleum Engineering":            "Engineering",
    "BSc Architecture":                     "Engineering",
    "BSc Urban and Regional Planning":      "Engineering",
    "BSc Quantity Surveying":               "Engineering",
    "BSc Renewable Energy Engineering":     "Engineering",

    # Natural Sciences
    "BSc Mathematics":                      "Natural Sciences",
    "BSc Statistics":                       "Natural Sciences",
    "BSc Physics":                          "Natural Sciences",
    "BSc Chemistry":                        "Natural Sciences",
    "BSc Biology":                          "Natural Sciences",
    "BSc Environmental Science":            "Natural Sciences",
    "BSc Biochemistry":                     "Natural Sciences",
    "BSc Biotechnology":                    "Natural Sciences",
    "BSc Microbiology":                     "Natural Sciences",
    "BSc Geography":                        "Natural Sciences",
    "BSc Geology":                          "Natural Sciences",
    "BSc Geophysics":                       "Natural Sciences",
    "BSc Actuarial Science":                "Natural Sciences",
    "BSc Artificial Chemistry":             "Natural Sciences",

    # Agriculture & Environment
    "BSc Agriculture":                      "Agriculture & Environment",
    "BSc Agricultural Science":             "Agriculture & Environment",
    "BSc Soil Science":                     "Agriculture & Environment",
    "BSc Fisheries":                        "Agriculture & Environment",
    "BSc Veterinary Medicine":              "Agriculture & Environment",
    "BSc Environmental Health":             "Agriculture & Environment",
    "BSc Food Science":                     "Agriculture & Environment",
    "BSc Nutrition and Dietetics":          "Agriculture & Environment",
    "BSc Human Nutrition":                  "Agriculture & Environment",
    "BSc Nutrition and Public Health":      "Agriculture & Environment",

    # Health Sciences
    "BSc Nursing":                          "Health Sciences",
    "BSc Public Health":                    "Health Sciences",
    "BSc Midwifery":                        "Health Sciences",
    "BSc Pharmacy":                         "Health Sciences",
    "BSc Physiotherapy":                    "Health Sciences",
    "BSc Radiography":                      "Health Sciences",
    "BSc Occupational Therapy":             "Health Sciences",
    "BSc Speech and Language Therapy":      "Health Sciences",
    "BSc Optometry":                        "Health Sciences",
    "BSc Biochemistry":                     "Health Sciences",  # duplicate, will be handled

    # Law
    "BSc Law":                              "Law",
    "LLB Law":                              "Law",
    "LLB Corporate Law":                    "Law",

    # Education
    "BSc Education (Mathematics)":          "Education",
    "BSc Education (Science)":              "Education",

    # Arts & Creative Studies
    "BSc Fine Arts":                        "Arts & Creative Studies",
    "BSc Fine & Applied Arts":              "Arts & Creative Studies",
    "BSc Theatre Arts":                     "Arts & Creative Studies",
    "BSc Music":                            "Arts & Creative Studies",
    "BSc Fashion & Textile Design":         "Arts & Creative Studies",
    "BSc Textile and Fashion Design":       "Arts & Creative Studies",
    "BSc Graphic Design":                   "Arts & Creative Studies",
    "BSc Animation & Visual Effects":       "Arts & Creative Studies",

    # Hospitality & Tourism
    "BSc Hospitality & Tourism Management": "Hospitality & Tourism",
    "BSc Hospitality Management":           "Hospitality & Tourism",
    "BSc Hotel and Catering Management":    "Hospitality & Tourism",
    "BSc Tourism Management":               "Hospitality & Tourism",
    "BSc Tourism and Events Management":    "Hospitality & Tourism",
}

# Icons per faculty
FACULTY_ICONS = {
    "Business & Management":    "briefcase",
    "Social Sciences & Humanities": "users",
    "Computing & Technology":   "laptop-code",
    "Engineering":              "cogs",
    "Natural Sciences":         "flask",
    "Agriculture & Environment":"leaf",
    "Health Sciences":          "heartbeat",
    "Law":                      "balance-scale",
    "Education":                "chalkboard-teacher",
    "Arts & Creative Studies":  "palette",
    "Hospitality & Tourism":    "concierge-bell",
}

FACULTY_COLORS = {
    "Business & Management":    "#f59e0b",
    "Social Sciences & Humanities": "#3b82f6",
    "Computing & Technology":   "#8b5cf6",
    "Engineering":              "#6b7280",
    "Natural Sciences":         "#10b981",
    "Agriculture & Environment":"#84cc16",
    "Health Sciences":          "#ef4444",
    "Law":                      "#1d4ed8",
    "Education":                "#f97316",
    "Arts & Creative Studies":  "#ec4899",
    "Hospitality & Tourism":    "#14b8a6",
}

PROGRAMME_ICONS = {
    "Computing & Technology":   "laptop-code",
    "Engineering":              "cogs",
    "Business & Management":    "chart-line",
    "Natural Sciences":         "atom",
    "Health Sciences":          "stethoscope",
    "Social Sciences & Humanities": "globe",
    "Agriculture & Environment":"seedling",
    "Law":                      "gavel",
    "Education":                "graduation-cap",
    "Arts & Creative Studies":  "paint-brush",
    "Hospitality & Tourism":    "hotel",
}

# Enrollment weights (for ordering)
ENROLLMENT = {
    "BSc Business Administration": 9, "BSc Accounting": 7, "BSc Marketing": 6,
    "BSc Human Resource Management": 5, "BSc Banking and Finance": 6,
    "BSc Supply Chain Management": 4, "BSc Entrepreneurship": 3,
    "BA Economics": 5, "BA Political Science": 5, "BA Sociology": 4,
    "BA Psychology": 4, "BA Communication Studies": 4, "BA History": 3,
    "BA English": 3, "BA Philosophy": 2, "BA Linguistics": 2,
    "BSc Computer Science": 7, "BSc Information Technology": 6,
    "BSc Software Engineering": 5, "BSc Data Science": 3,
    "BSc Artificial Intelligence": 2, "BSc Cybersecurity": 3,
    "BSc Electrical & Electronic Engineering": 4, "BSc Mechanical Engineering": 3,
    "BSc Civil Engineering": 3, "BSc Petroleum Engineering": 2,
    "BSc Architecture": 2, "BSc Urban and Regional Planning": 2,
    "BSc Mathematics": 4, "BSc Statistics": 3, "BSc Physics": 3,
    "BSc Chemistry": 3, "BSc Biology": 3, "BSc Environmental Science": 3,
    "BSc Agriculture": 3, "BSc Agribusiness": 3, "BSc Soil Science": 1,
    "BSc Fisheries": 1, "BSc Veterinary Medicine": 1, "BSc Nursing": 6,
    "BSc Public Health": 4, "BSc Midwifery": 2, "BSc Nutrition and Dietetics": 2,
    "BSc Pharmacy": 3, "BSc Physiotherapy": 2, "BSc Radiography": 2,
    "BSc Occupational Therapy": 1, "BSc Speech and Language Therapy": 1,
    "BSc Fine Arts": 2, "BSc Theatre Arts": 2, "BSc Music": 2,
    "BSc Fashion & Textile Design": 1, "BSc Hospitality & Tourism Management": 3,
    "BSc Hotel and Catering Management": 2, "BSc Tourism and Events Management": 3,
    "LLB Law": 5, "BSc Criminology and Security Studies": 2,
    "BSc Education (Mathematics)": 4, "BSc Education (Science)": 4,
}

CSV_DATA = """Programme,Level,Year,Semester,Course Code,Course Name
BSc Computer Science,Undergraduate,1,1,CS101,Introduction to Programming
BSc Computer Science,Undergraduate,1,1,CS102,Discrete Mathematics
BSc Computer Science,Undergraduate,1,1,CS103,Computer Systems Fundamentals
BSc Computer Science,Undergraduate,1,2,CS104,Object Oriented Programming
BSc Computer Science,Undergraduate,1,2,CS105,Linear Algebra for Computing
BSc Computer Science,Undergraduate,1,2,CS106,Digital Logic
BSc Computer Science,Undergraduate,2,1,CS201,Data Structures and Algorithms
BSc Computer Science,Undergraduate,2,1,CS202,Operating Systems
BSc Computer Science,Undergraduate,2,2,CS203,Database Systems
BSc Computer Science,Undergraduate,2,2,CS204,Software Engineering
BSc Computer Science,Undergraduate,3,1,CS301,Artificial Intelligence
BSc Computer Science,Undergraduate,3,2,CS302,Computer Networks
BSc Computer Science,Undergraduate,4,1,CS401,Machine Learning
BSc Computer Science,Undergraduate,4,2,CS402,Final Year Project
BSc Information Technology,Undergraduate,1,1,IT101,Introduction to IT
BSc Information Technology,Undergraduate,1,2,IT103,Database Fundamentals
BSc Information Technology,Undergraduate,2,1,IT201,System Analysis and Design
BSc Information Technology,Undergraduate,2,2,IT202,Networking Fundamentals
BSc Information Technology,Undergraduate,3,1,IT301,Web Application Development
BSc Information Technology,Undergraduate,3,2,IT302,Information Security
BSc Information Technology,Undergraduate,4,1,IT401,Cloud Computing
BSc Information Technology,Undergraduate,4,2,IT402,Capstone Project
BSc Software Engineering,Undergraduate,1,1,SE101,Introduction to Software Engineering
BSc Software Engineering,Undergraduate,1,2,SE102,Programming Fundamentals
BSc Software Engineering,Undergraduate,2,1,SE201,Object-Oriented Programming
BSc Software Engineering,Undergraduate,2,2,SE202,Database Systems
BSc Software Engineering,Undergraduate,3,1,SE301,Software Project Management
BSc Software Engineering,Undergraduate,3,2,SE302,Software Quality Assurance
BSc Software Engineering,Undergraduate,4,1,SE401,Agile Methodologies
BSc Software Engineering,Undergraduate,4,2,SE402,Capstone Project
BSc Data Science,Undergraduate,1,1,DS101,Introduction to Data Science
BSc Data Science,Undergraduate,1,2,DS102,Statistics for Data Science
BSc Data Science,Undergraduate,2,1,DS201,Machine Learning I
BSc Data Science,Undergraduate,2,2,DS202,Database Systems
BSc Data Science,Undergraduate,3,1,DS301,Data Mining
BSc Data Science,Undergraduate,3,2,DS302,Big Data Analytics
BSc Data Science,Undergraduate,4,1,DS401,AI and Deep Learning
BSc Data Science,Undergraduate,4,2,DS402,Data Science Project
BSc Artificial Intelligence,Undergraduate,1,1,AI101,Introduction to AI
BSc Artificial Intelligence,Undergraduate,1,2,AI102,Programming for AI
BSc Artificial Intelligence,Undergraduate,2,1,AI201,Machine Learning
BSc Artificial Intelligence,Undergraduate,2,2,AI202,Data Structures for AI
BSc Artificial Intelligence,Undergraduate,3,1,AI301,Computer Vision
BSc Artificial Intelligence,Undergraduate,3,2,AI302,Natural Language Processing
BSc Artificial Intelligence,Undergraduate,4,1,AI401,AI Ethics and Policy
BSc Artificial Intelligence,Undergraduate,4,2,AI402,AI Project
BSc Cybersecurity,Undergraduate,1,1,CSY101,Introduction to Cybersecurity
BSc Cybersecurity,Undergraduate,1,2,CSY102,Computer Networks
BSc Cybersecurity,Undergraduate,2,1,CSY201,Network Security
BSc Cybersecurity,Undergraduate,2,2,CSY202,Cryptography
BSc Cybersecurity,Undergraduate,3,1,CSY301,Penetration Testing
BSc Cybersecurity,Undergraduate,3,2,CSY302,Digital Forensics
BSc Cybersecurity,Undergraduate,4,1,CSY401,Cybersecurity Policy
BSc Cybersecurity,Undergraduate,4,2,CSY402,Cybersecurity Project
BSc Electrical & Electronic Engineering,Undergraduate,1,1,EEE101,Circuit Theory
BSc Electrical & Electronic Engineering,Undergraduate,1,2,EEE102,Electronics I
BSc Electrical & Electronic Engineering,Undergraduate,2,1,EEE201,Signals and Systems
BSc Electrical & Electronic Engineering,Undergraduate,2,2,EEE202,Digital Electronics
BSc Electrical & Electronic Engineering,Undergraduate,3,1,EEE301,Control Systems
BSc Electrical & Electronic Engineering,Undergraduate,3,2,EEE302,Power Systems
BSc Electrical & Electronic Engineering,Undergraduate,4,1,EEE401,Electrical Project Management
BSc Electrical & Electronic Engineering,Undergraduate,4,2,EEE402,Electrical Engineering Project
BSc Mechanical Engineering,Undergraduate,1,1,ME101,Thermodynamics I
BSc Mechanical Engineering,Undergraduate,1,2,ME102,Engineering Drawing
BSc Mechanical Engineering,Undergraduate,2,1,ME201,Mechanics of Materials
BSc Mechanical Engineering,Undergraduate,2,2,ME202,Fluid Mechanics
BSc Mechanical Engineering,Undergraduate,3,1,ME301,Heat Transfer
BSc Mechanical Engineering,Undergraduate,3,2,ME302,Manufacturing Processes
BSc Mechanical Engineering,Undergraduate,4,1,ME401,Project Management
BSc Mechanical Engineering,Undergraduate,4,2,ME402,Mechanical Engineering Project
BSc Civil Engineering,Undergraduate,1,1,CE101,Engineering Mechanics
BSc Civil Engineering,Undergraduate,1,2,CE102,Statics and Dynamics
BSc Civil Engineering,Undergraduate,2,1,CE201,Structural Analysis
BSc Civil Engineering,Undergraduate,2,2,CE202,Fluid Mechanics
BSc Civil Engineering,Undergraduate,3,1,CE301,Geotechnical Engineering
BSc Civil Engineering,Undergraduate,3,2,CE302,Transportation Engineering
BSc Civil Engineering,Undergraduate,4,1,CE401,Construction Management
BSc Civil Engineering,Undergraduate,4,2,CE402,Civil Engineering Project
BSc Petroleum Engineering,Undergraduate,1,1,PE101,Introduction to Petroleum Engineering
BSc Petroleum Engineering,Undergraduate,1,2,PE102,Engineering Mathematics
BSc Petroleum Engineering,Undergraduate,2,1,PE201,Reservoir Engineering I
BSc Petroleum Engineering,Undergraduate,2,2,PE202,Fluid Mechanics
BSc Petroleum Engineering,Undergraduate,3,1,PE301,Drilling Engineering
BSc Petroleum Engineering,Undergraduate,3,2,PE302,Production Engineering
BSc Petroleum Engineering,Undergraduate,4,1,PE401,Petroleum Project Management
BSc Petroleum Engineering,Undergraduate,4,2,PE402,Petroleum Engineering Project
BSc Architecture,Undergraduate,1,1,AR101,Introduction to Architecture
BSc Architecture,Undergraduate,1,2,AR102,Design Fundamentals
BSc Architecture,Undergraduate,2,1,AR201,Building Technology
BSc Architecture,Undergraduate,2,2,AR202,Construction Materials
BSc Architecture,Undergraduate,3,1,AR301,Architectural Design III
BSc Architecture,Undergraduate,3,2,AR302,Urban Architecture
BSc Architecture,Undergraduate,4,1,AR401,Professional Practice
BSc Architecture,Undergraduate,4,2,AR402,Architecture Thesis
BSc Urban and Regional Planning,Undergraduate,1,1,URP101,Introduction to Urban Planning
BSc Urban and Regional Planning,Undergraduate,1,2,URP102,Cartography and GIS
BSc Urban and Regional Planning,Undergraduate,2,1,URP201,Urban Design
BSc Urban and Regional Planning,Undergraduate,2,2,URP202,Land Use Planning
BSc Urban and Regional Planning,Undergraduate,3,1,URP301,Transportation Planning
BSc Urban and Regional Planning,Undergraduate,3,2,URP302,Environmental Planning
BSc Urban and Regional Planning,Undergraduate,4,1,URP401,Urban Policy and Governance
BSc Urban and Regional Planning,Undergraduate,4,2,URP402,Planning Project
BSc Business Administration,Undergraduate,1,1,BA101,Principles of Management
BSc Business Administration,Undergraduate,1,2,BA102,Business Communication
BSc Business Administration,Undergraduate,2,1,BA201,Marketing Principles
BSc Business Administration,Undergraduate,2,2,BA202,Human Resource Management
BSc Business Administration,Undergraduate,3,1,BA301,Operations Management
BSc Business Administration,Undergraduate,3,2,BA302,Strategic Management
BSc Business Administration,Undergraduate,4,1,BA401,Entrepreneurship
BSc Business Administration,Undergraduate,4,2,BA402,Business Strategy Project
BSc Accounting,Undergraduate,1,1,AC101,Principles of Accounting
BSc Accounting,Undergraduate,1,2,AC102,Financial Accounting
BSc Accounting,Undergraduate,2,1,AC201,Cost Accounting
BSc Accounting,Undergraduate,2,2,AC202,Taxation
BSc Accounting,Undergraduate,3,1,AC301,Auditing
BSc Accounting,Undergraduate,3,2,AC302,Corporate Finance
BSc Accounting,Undergraduate,4,1,AC401,Advanced Financial Accounting
BSc Accounting,Undergraduate,4,2,AC402,Accounting Research Project
BSc Marketing,Undergraduate,1,1,MK101,Principles of Marketing
BSc Marketing,Undergraduate,1,2,MK102,Consumer Behaviour
BSc Marketing,Undergraduate,2,1,MK201,Marketing Research
BSc Marketing,Undergraduate,2,2,MK202,Digital Marketing
BSc Marketing,Undergraduate,3,1,MK301,Brand Management
BSc Marketing,Undergraduate,3,2,MK302,Sales Management
BSc Marketing,Undergraduate,4,1,MK401,Strategic Marketing
BSc Marketing,Undergraduate,4,2,MK402,Marketing Project
BSc Human Resource Management,Undergraduate,1,1,HR101,Introduction to HR
BSc Human Resource Management,Undergraduate,1,2,HR102,Organizational Behavior
BSc Human Resource Management,Undergraduate,2,1,HR201,Employee Relations
BSc Human Resource Management,Undergraduate,2,2,HR202,Recruitment and Selection
BSc Human Resource Management,Undergraduate,3,1,HR301,Training and Development
BSc Human Resource Management,Undergraduate,3,2,HR302,Performance Management
BSc Human Resource Management,Undergraduate,4,1,HR401,Compensation Management
BSc Human Resource Management,Undergraduate,4,2,HR402,HR Project
BSc Banking and Finance,Undergraduate,1,1,BF101,Principles of Banking
BSc Banking and Finance,Undergraduate,1,2,BF102,Financial Accounting
BSc Banking and Finance,Undergraduate,2,1,BF201,Corporate Finance
BSc Banking and Finance,Undergraduate,2,2,BF202,Investment Analysis
BSc Banking and Finance,Undergraduate,3,1,BF301,Risk Management
BSc Banking and Finance,Undergraduate,3,2,BF302,Banking Operations
BSc Banking and Finance,Undergraduate,4,1,BF401,Financial Markets
BSc Banking and Finance,Undergraduate,4,2,BF402,Finance Project
BSc Supply Chain Management,Undergraduate,1,1,SCM101,Introduction to Supply Chain
BSc Supply Chain Management,Undergraduate,1,2,SCM102,Logistics Fundamentals
BSc Supply Chain Management,Undergraduate,2,1,SCM201,Procurement Management
BSc Supply Chain Management,Undergraduate,2,2,SCM202,Operations Management
BSc Supply Chain Management,Undergraduate,3,1,SCM301,Inventory Management
BSc Supply Chain Management,Undergraduate,3,2,SCM302,Supply Chain Analytics
BSc Supply Chain Management,Undergraduate,4,1,SCM401,Strategic Supply Chain
BSc Supply Chain Management,Undergraduate,4,2,SCM402,Supply Chain Project
BSc Entrepreneurship,Undergraduate,1,1,ENP101,Principles of Entrepreneurship
BSc Entrepreneurship,Undergraduate,1,2,ENP102,Business Idea Development
BSc Entrepreneurship,Undergraduate,2,1,ENP201,Small Business Management
BSc Entrepreneurship,Undergraduate,2,2,ENP202,Innovation Management
BSc Entrepreneurship,Undergraduate,3,1,ENP301,Entrepreneurial Finance
BSc Entrepreneurship,Undergraduate,3,2,ENP302,Marketing for Entrepreneurs
BSc Entrepreneurship,Undergraduate,4,1,ENP401,Scaling Businesses
BSc Entrepreneurship,Undergraduate,4,2,ENP402,Entrepreneurship Project
BA Economics,Undergraduate,1,1,EC101,Microeconomics I
BA Economics,Undergraduate,1,2,EC102,Macroeconomics I
BA Economics,Undergraduate,2,1,EC201,Intermediate Microeconomics
BA Economics,Undergraduate,2,2,EC202,Intermediate Macroeconomics
BA Economics,Undergraduate,3,1,EC301,Econometrics
BA Economics,Undergraduate,3,2,EC302,Development Economics
BA Economics,Undergraduate,4,1,EC401,International Economics
BA Economics,Undergraduate,4,2,EC402,Economics Research Project
BA Political Science,Undergraduate,1,1,PS101,Introduction to Political Science
BA Political Science,Undergraduate,1,2,PS102,African Politics
BA Political Science,Undergraduate,2,1,PS201,Comparative Politics
BA Political Science,Undergraduate,2,2,PS202,Public Administration
BA Political Science,Undergraduate,3,1,PS301,International Relations
BA Political Science,Undergraduate,3,2,PS302,Political Theory
BA Political Science,Undergraduate,4,1,PS401,Public Policy Analysis
BA Political Science,Undergraduate,4,2,PS402,Political Science Thesis
BA Sociology,Undergraduate,1,1,SO101,Introduction to Sociology
BA Sociology,Undergraduate,1,2,SO102,Social Problems
BA Sociology,Undergraduate,2,1,SO201,Social Theory
BA Sociology,Undergraduate,2,2,SO202,Urban Sociology
BA Sociology,Undergraduate,3,1,SO301,Gender Studies
BA Sociology,Undergraduate,3,2,SO302,Research Methods
BA Sociology,Undergraduate,4,1,SO401,Development Sociology
BA Sociology,Undergraduate,4,2,SO402,Sociology Project
BA Psychology,Undergraduate,1,1,PY101,Introduction to Psychology
BA Psychology,Undergraduate,1,2,PY102,Developmental Psychology
BA Psychology,Undergraduate,2,1,PY201,Cognitive Psychology
BA Psychology,Undergraduate,2,2,PY202,Abnormal Psychology
BA Psychology,Undergraduate,3,1,PY301,Social Psychology
BA Psychology,Undergraduate,3,2,PY302,Research Methods in Psychology
BA Psychology,Undergraduate,4,1,PY401,Clinical Psychology
BA Psychology,Undergraduate,4,2,PY402,Psychology Thesis
BA Communication Studies,Undergraduate,1,1,CM101,Introduction to Communication
BA Communication Studies,Undergraduate,1,2,CM102,Media Writing
BA Communication Studies,Undergraduate,2,1,CM201,Journalism Principles
BA Communication Studies,Undergraduate,2,2,CM202,Public Relations
BA Communication Studies,Undergraduate,3,1,CM301,Broadcast Journalism
BA Communication Studies,Undergraduate,3,2,CM302,Media Ethics
BA Communication Studies,Undergraduate,4,1,CM401,Strategic Communication
BA Communication Studies,Undergraduate,4,2,CM402,Communication Research Project
BA History,Undergraduate,1,1,HI101,Introduction to World History
BA History,Undergraduate,1,2,HI102,African History
BA History,Undergraduate,2,1,HI201,History of Ghana
BA History,Undergraduate,2,2,HI202,Colonial Africa
BA History,Undergraduate,3,1,HI301,Modern African History
BA History,Undergraduate,3,2,HI302,Historical Research Methods
BA History,Undergraduate,4,1,HI401,Global History
BA History,Undergraduate,4,2,HI402,History Thesis
BA English,Undergraduate,1,1,EN101,Introduction to Literature
BA English,Undergraduate,1,2,EN102,Academic Writing
BA English,Undergraduate,2,1,EN201,African Literature
BA English,Undergraduate,2,2,EN202,Literary Theory
BA English,Undergraduate,3,1,EN301,Postcolonial Literature
BA English,Undergraduate,3,2,EN302,Creative Writing
BA English,Undergraduate,4,1,EN401,Advanced Literary Studies
BA English,Undergraduate,4,2,EN402,English Thesis
BA Philosophy,Undergraduate,1,1,PHL101,Introduction to Philosophy
BA Philosophy,Undergraduate,1,2,PHL102,Ethics
BA Philosophy,Undergraduate,2,1,PHL201,Logic
BA Philosophy,Undergraduate,2,2,PHL202,Political Philosophy
BA Philosophy,Undergraduate,3,1,PHL301,Philosophy of Mind
BA Philosophy,Undergraduate,3,2,PHL302,Philosophy of Science
BA Philosophy,Undergraduate,4,1,PHL401,Contemporary Philosophy
BA Philosophy,Undergraduate,4,2,PHL402,Philosophy Thesis
BA Linguistics,Undergraduate,1,1,LG101,Introduction to Linguistics
BA Linguistics,Undergraduate,1,2,LG102,Phonetics
BA Linguistics,Undergraduate,2,1,LG201,Phonology
BA Linguistics,Undergraduate,2,2,LG202,Syntax
BA Linguistics,Undergraduate,3,1,LG301,Sociolinguistics
BA Linguistics,Undergraduate,3,2,LG302,Language Acquisition
BA Linguistics,Undergraduate,4,1,LG401,Applied Linguistics
BA Linguistics,Undergraduate,4,2,LG402,Linguistics Thesis
BSc Mathematics,Undergraduate,1,1,MA101,Calculus I
BSc Mathematics,Undergraduate,1,2,MA102,Linear Algebra
BSc Mathematics,Undergraduate,2,1,MA201,Calculus II
BSc Mathematics,Undergraduate,2,2,MA202,Differential Equations
BSc Mathematics,Undergraduate,3,1,MA301,Probability and Statistics
BSc Mathematics,Undergraduate,3,2,MA302,Abstract Algebra
BSc Mathematics,Undergraduate,4,1,MA401,Real Analysis
BSc Mathematics,Undergraduate,4,2,MA402,Mathematics Project
BSc Statistics,Undergraduate,1,1,ST101,Introduction to Statistics
BSc Statistics,Undergraduate,1,2,ST102,Probability Theory
BSc Statistics,Undergraduate,2,1,ST201,Regression Analysis
BSc Statistics,Undergraduate,2,2,ST202,Multivariate Statistics
BSc Statistics,Undergraduate,3,1,ST301,Time Series Analysis
BSc Statistics,Undergraduate,3,2,ST302,Statistical Computing
BSc Statistics,Undergraduate,4,1,ST401,Advanced Statistical Methods
BSc Statistics,Undergraduate,4,2,ST402,Statistics Project
BSc Physics,Undergraduate,1,1,PHYS101,Classical Mechanics
BSc Physics,Undergraduate,1,2,PHYS102,Electricity and Magnetism
BSc Physics,Undergraduate,2,1,PHYS201,Quantum Mechanics
BSc Physics,Undergraduate,2,2,PHYS202,Thermodynamics
BSc Physics,Undergraduate,3,1,PHYS301,Solid State Physics
BSc Physics,Undergraduate,3,2,PHYS302,Nuclear Physics
BSc Physics,Undergraduate,4,1,PHYS401,Particle Physics
BSc Physics,Undergraduate,4,2,PHYS402,Physics Research Project
BSc Chemistry,Undergraduate,1,1,CH101,General Chemistry
BSc Chemistry,Undergraduate,1,2,CH102,Organic Chemistry I
BSc Chemistry,Undergraduate,2,1,CH201,Inorganic Chemistry
BSc Chemistry,Undergraduate,2,2,CH202,Physical Chemistry
BSc Chemistry,Undergraduate,3,1,CH301,Analytical Chemistry
BSc Chemistry,Undergraduate,3,2,CH302,Biochemistry
BSc Chemistry,Undergraduate,4,1,CH401,Industrial Chemistry
BSc Chemistry,Undergraduate,4,2,CH402,Chemistry Project
BSc Biology,Undergraduate,1,1,BI101,General Biology
BSc Biology,Undergraduate,1,2,BI102,Cell Biology
BSc Biology,Undergraduate,2,1,BI201,Genetics
BSc Biology,Undergraduate,2,2,BI202,Microbiology
BSc Biology,Undergraduate,3,1,BI301,Ecology
BSc Biology,Undergraduate,3,2,BI302,Plant Physiology
BSc Biology,Undergraduate,4,1,BI401,Molecular Biology
BSc Biology,Undergraduate,4,2,BI402,Biology Research Project
BSc Environmental Science,Undergraduate,1,1,ES101,Introduction to Environmental Science
BSc Environmental Science,Undergraduate,1,2,ES102,Ecosystem Dynamics
BSc Environmental Science,Undergraduate,2,1,ES201,Environmental Chemistry
BSc Environmental Science,Undergraduate,2,2,ES202,Environmental Microbiology
BSc Environmental Science,Undergraduate,3,1,ES301,Climate Change Science
BSc Environmental Science,Undergraduate,3,2,ES302,Pollution Control
BSc Environmental Science,Undergraduate,4,1,ES401,Environmental Impact Assessment
BSc Environmental Science,Undergraduate,4,2,ES402,Environmental Project
BSc Agriculture,Undergraduate,1,1,AG101,Introduction to Agriculture
BSc Agriculture,Undergraduate,1,2,AG102,Soil Science
BSc Agriculture,Undergraduate,2,1,AG201,Crop Science
BSc Agriculture,Undergraduate,2,2,AG202,Animal Science
BSc Agriculture,Undergraduate,3,1,AG301,Agricultural Economics
BSc Agriculture,Undergraduate,3,2,AG302,Plant Breeding
BSc Agriculture,Undergraduate,4,1,AG401,Agricultural Extension
BSc Agriculture,Undergraduate,4,2,AG402,Agriculture Project
BSc Agribusiness,Undergraduate,1,1,AB101,Principles of Agribusiness
BSc Agribusiness,Undergraduate,1,2,AB102,Agricultural Marketing
BSc Agribusiness,Undergraduate,2,1,AB201,Farm Management
BSc Agribusiness,Undergraduate,2,2,AB202,Agricultural Finance
BSc Agribusiness,Undergraduate,3,1,AB301,Supply Chain in Agriculture
BSc Agribusiness,Undergraduate,3,2,AB302,Agribusiness Strategy
BSc Agribusiness,Undergraduate,4,1,AB401,Agribusiness Policy
BSc Agribusiness,Undergraduate,4,2,AB402,Agribusiness Project
BSc Soil Science,Undergraduate,1,1,SS101,Introduction to Soil Science
BSc Soil Science,Undergraduate,1,2,SS102,Soil Chemistry
BSc Soil Science,Undergraduate,2,1,SS201,Soil Physics
BSc Soil Science,Undergraduate,2,2,SS202,Soil Fertility Management
BSc Soil Science,Undergraduate,3,1,SS301,Soil and Water Conservation
BSc Soil Science,Undergraduate,3,2,SS302,Land Use Planning
BSc Soil Science,Undergraduate,4,1,SS401,Research Methods
BSc Soil Science,Undergraduate,4,2,SS402,Soil Science Project
BSc Fisheries,Undergraduate,1,1,FSH101,Introduction to Fisheries
BSc Fisheries,Undergraduate,1,2,FSH102,Aquatic Biology
BSc Fisheries,Undergraduate,2,1,FSH201,Fish Breeding
BSc Fisheries,Undergraduate,2,2,FSH202,Fish Nutrition
BSc Fisheries,Undergraduate,3,1,FSH301,Fisheries Management
BSc Fisheries,Undergraduate,3,2,FSH302,Aquaculture
BSc Fisheries,Undergraduate,4,1,FSH401,Fisheries Research Methods
BSc Fisheries,Undergraduate,4,2,FSH402,Fisheries Project
BSc Veterinary Medicine,Undergraduate,1,1,VM101,Introduction to Veterinary Science
BSc Veterinary Medicine,Undergraduate,1,2,VM102,Animal Anatomy
BSc Veterinary Medicine,Undergraduate,2,1,VM201,Animal Physiology
BSc Veterinary Medicine,Undergraduate,2,2,VM202,Animal Nutrition
BSc Veterinary Medicine,Undergraduate,3,1,VM301,Pathology
BSc Veterinary Medicine,Undergraduate,3,2,VM302,Clinical Veterinary Practice
BSc Veterinary Medicine,Undergraduate,4,1,VM401,Veterinary Pharmacology
BSc Veterinary Medicine,Undergraduate,4,2,VM402,Veterinary Project
BSc Nursing,Undergraduate,1,1,NS101,Anatomy and Physiology I
BSc Nursing,Undergraduate,1,2,NS102,Basic Nursing Skills
BSc Nursing,Undergraduate,2,1,NS201,Medical-Surgical Nursing I
BSc Nursing,Undergraduate,2,2,NS202,Pharmacology for Nursing
BSc Nursing,Undergraduate,3,1,NS301,Medical-Surgical Nursing II
BSc Nursing,Undergraduate,3,2,NS302,Mental Health Nursing
BSc Nursing,Undergraduate,4,1,NS401,Community Health Nursing
BSc Nursing,Undergraduate,4,2,NS402,Nursing Research Project
BSc Public Health,Undergraduate,1,1,PH101,Introduction to Public Health
BSc Public Health,Undergraduate,1,2,PH102,Epidemiology I
BSc Public Health,Undergraduate,2,1,PH201,Biostatistics
BSc Public Health,Undergraduate,2,2,PH202,Health Promotion
BSc Public Health,Undergraduate,3,1,PH301,Environmental Health
BSc Public Health,Undergraduate,3,2,PH302,Global Health
BSc Public Health,Undergraduate,4,1,PH401,Health Policy
BSc Public Health,Undergraduate,4,2,PH402,Public Health Project
BSc Midwifery,Undergraduate,1,1,MW101,Anatomy and Physiology for Midwifery
BSc Midwifery,Undergraduate,1,2,MW102,Fundamentals of Midwifery
BSc Midwifery,Undergraduate,2,1,MW201,Obstetrics I
BSc Midwifery,Undergraduate,2,2,MW202,Community Midwifery
BSc Midwifery,Undergraduate,3,1,MW301,Obstetrics II
BSc Midwifery,Undergraduate,3,2,MW302,Neonatal Care
BSc Midwifery,Undergraduate,4,1,MW401,Advanced Midwifery
BSc Midwifery,Undergraduate,4,2,MW402,Midwifery Project
BSc Nutrition and Dietetics,Undergraduate,1,1,ND101,Human Nutrition
BSc Nutrition and Dietetics,Undergraduate,1,2,ND102,Food Composition
BSc Nutrition and Dietetics,Undergraduate,2,1,ND201,Nutritional Biochemistry
BSc Nutrition and Dietetics,Undergraduate,2,2,ND202,Dietetics
BSc Nutrition and Dietetics,Undergraduate,3,1,ND301,Public Health Nutrition
BSc Nutrition and Dietetics,Undergraduate,3,2,ND302,Clinical Nutrition
BSc Nutrition and Dietetics,Undergraduate,4,1,ND401,Nutrition Policy
BSc Nutrition and Dietetics,Undergraduate,4,2,ND402,Nutrition Project
BSc Pharmacy,Undergraduate,1,1,PHM101,Pharmaceutical Chemistry I
BSc Pharmacy,Undergraduate,1,2,PHM102,Biochemistry for Pharmacy
BSc Pharmacy,Undergraduate,2,1,PHM201,Pharmacology I
BSc Pharmacy,Undergraduate,2,2,PHM202,Pharmaceutics I
BSc Pharmacy,Undergraduate,3,1,PHM301,Pharmacology II
BSc Pharmacy,Undergraduate,3,2,PHM302,Pharmaceutics II
BSc Pharmacy,Undergraduate,4,1,PHM401,Clinical Pharmacy
BSc Pharmacy,Undergraduate,4,2,PHM402,Pharmacy Project
BSc Physiotherapy,Undergraduate,1,1,PT101,Human Anatomy
BSc Physiotherapy,Undergraduate,1,2,PT102,Physiology
BSc Physiotherapy,Undergraduate,2,1,PT201,Kinesiology
BSc Physiotherapy,Undergraduate,2,2,PT202,Exercise Therapy
BSc Physiotherapy,Undergraduate,3,1,PT301,Neurological Physiotherapy
BSc Physiotherapy,Undergraduate,3,2,PT302,Cardiopulmonary Physiotherapy
BSc Physiotherapy,Undergraduate,4,1,PT401,Clinical Practice I
BSc Physiotherapy,Undergraduate,4,2,PT402,Clinical Practice II
BSc Radiography,Undergraduate,1,1,RD101,Anatomy and Physiology
BSc Radiography,Undergraduate,1,2,RD102,Medical Imaging Fundamentals
BSc Radiography,Undergraduate,2,1,RD201,Diagnostic Radiography I
BSc Radiography,Undergraduate,2,2,RD202,Diagnostic Radiography II
BSc Radiography,Undergraduate,3,1,RD301,Medical Physics
BSc Radiography,Undergraduate,3,2,RD302,Radiation Safety
BSc Radiography,Undergraduate,4,1,RD401,Advanced Imaging Techniques
BSc Radiography,Undergraduate,4,2,RD402,Radiography Project
BSc Occupational Therapy,Undergraduate,1,1,OT101,Introduction to Occupational Therapy
BSc Occupational Therapy,Undergraduate,1,2,OT102,Human Anatomy
BSc Occupational Therapy,Undergraduate,2,1,OT201,Physiology for OT
BSc Occupational Therapy,Undergraduate,2,2,OT202,Activity Analysis
BSc Occupational Therapy,Undergraduate,3,1,OT301,Pediatric OT
BSc Occupational Therapy,Undergraduate,3,2,OT302,Neurological OT
BSc Occupational Therapy,Undergraduate,4,1,OT401,Clinical Practice I
BSc Occupational Therapy,Undergraduate,4,2,OT402,Occupational Therapy Project
BSc Speech and Language Therapy,Undergraduate,1,1,SL101,Introduction to Speech Therapy
BSc Speech and Language Therapy,Undergraduate,1,2,SL102,Human Anatomy and Physiology
BSc Speech and Language Therapy,Undergraduate,2,1,SL201,Phonetics and Phonology
BSc Speech and Language Therapy,Undergraduate,2,2,SL202,Language Development
BSc Speech and Language Therapy,Undergraduate,3,1,SL301,Clinical Speech Therapy I
BSc Speech and Language Therapy,Undergraduate,3,2,SL302,Clinical Speech Therapy II
BSc Speech and Language Therapy,Undergraduate,4,1,SL401,Advanced Speech Therapy
BSc Speech and Language Therapy,Undergraduate,4,2,SL402,Speech Therapy Project
BSc Fine Arts,Undergraduate,1,1,FA101,Drawing and Painting I
BSc Fine Arts,Undergraduate,1,2,FA102,Sculpture I
BSc Fine Arts,Undergraduate,2,1,FA201,Drawing and Painting II
BSc Fine Arts,Undergraduate,2,2,FA202,Sculpture II
BSc Fine Arts,Undergraduate,3,1,FA301,Printmaking
BSc Fine Arts,Undergraduate,3,2,FA302,Art History
BSc Fine Arts,Undergraduate,4,1,FA401,Studio Practice
BSc Fine Arts,Undergraduate,4,2,FA402,Final Art Project
BSc Theatre Arts,Undergraduate,1,1,TA101,Introduction to Theatre
BSc Theatre Arts,Undergraduate,1,2,TA102,Stagecraft
BSc Theatre Arts,Undergraduate,2,1,TA201,Acting I
BSc Theatre Arts,Undergraduate,2,2,TA202,Directing I
BSc Theatre Arts,Undergraduate,3,1,TA301,Acting II
BSc Theatre Arts,Undergraduate,3,2,TA302,Directing II
BSc Theatre Arts,Undergraduate,4,1,TA401,Theatre Production
BSc Theatre Arts,Undergraduate,4,2,TA402,Theatre Project
BSc Music,Undergraduate,1,1,MU101,Music Theory I
BSc Music,Undergraduate,1,2,MU102,Introduction to Music
BSc Music,Undergraduate,2,1,MU201,Music History
BSc Music,Undergraduate,2,2,MU202,Instrumental Practice
BSc Music,Undergraduate,3,1,MU301,Composition
BSc Music,Undergraduate,3,2,MU302,Conducting
BSc Music,Undergraduate,4,1,MU401,Music Research
BSc Music,Undergraduate,4,2,MU402,Music Project
BSc Fashion & Textile Design,Undergraduate,1,1,FTD101,Introduction to Fashion
BSc Fashion & Textile Design,Undergraduate,1,2,FTD102,Textile Technology
BSc Fashion & Textile Design,Undergraduate,2,1,FTD201,Garment Construction
BSc Fashion & Textile Design,Undergraduate,2,2,FTD202,Fashion Illustration
BSc Fashion & Textile Design,Undergraduate,3,1,FTD301,Fashion Marketing
BSc Fashion & Textile Design,Undergraduate,3,2,FTD302,Creative Fashion Design
BSc Fashion & Textile Design,Undergraduate,4,1,FTD401,Fashion Project I
BSc Fashion & Textile Design,Undergraduate,4,2,FTD402,Fashion Project II
BSc Hospitality & Tourism Management,Undergraduate,1,1,HTM101,Introduction to Hospitality
BSc Hospitality & Tourism Management,Undergraduate,1,2,HTM102,Food and Beverage Operations
BSc Hospitality & Tourism Management,Undergraduate,2,1,HTM201,Lodging Management
BSc Hospitality & Tourism Management,Undergraduate,2,2,HTM202,Event Planning
BSc Hospitality & Tourism Management,Undergraduate,3,1,HTM301,Tourism Marketing
BSc Hospitality & Tourism Management,Undergraduate,3,2,HTM302,Sustainable Hospitality
BSc Hospitality & Tourism Management,Undergraduate,4,1,HTM401,Hospitality Research
BSc Hospitality & Tourism Management,Undergraduate,4,2,HTM402,Hospitality Project
BSc Hotel and Catering Management,Undergraduate,1,1,HCM101,Introduction to Hotel Management
BSc Hotel and Catering Management,Undergraduate,1,2,HCM102,Food Production I
BSc Hotel and Catering Management,Undergraduate,2,1,HCM201,Food Production II
BSc Hotel and Catering Management,Undergraduate,2,2,HCM202,Front Office Operations
BSc Hotel and Catering Management,Undergraduate,3,1,HCM301,Event Management
BSc Hotel and Catering Management,Undergraduate,3,2,HCM302,Hospitality Marketing
BSc Hotel and Catering Management,Undergraduate,4,1,HCM401,Hospitality Research
BSc Hotel and Catering Management,Undergraduate,4,2,HCM402,Hotel Project
BSc Tourism and Events Management,Undergraduate,1,1,TE101,Introduction to Tourism
BSc Tourism and Events Management,Undergraduate,1,2,TE102,Event Management Basics
BSc Tourism and Events Management,Undergraduate,2,1,TE201,Destination Management
BSc Tourism and Events Management,Undergraduate,2,2,TE202,Hospitality Operations
BSc Tourism and Events Management,Undergraduate,3,1,TE301,Sustainable Tourism
BSc Tourism and Events Management,Undergraduate,3,2,TE302,Event Marketing
BSc Tourism and Events Management,Undergraduate,4,1,TE401,Strategic Event Management
BSc Tourism and Events Management,Undergraduate,4,2,TE402,Tourism Project
LLB Law,Undergraduate,1,1,LAW101,Introduction to Law
LLB Law,Undergraduate,1,2,LAW102,Constitutional Law I
LLB Law,Undergraduate,2,1,LAW201,Criminal Law
LLB Law,Undergraduate,2,2,LAW202,Contract Law
LLB Law,Undergraduate,3,1,LAW301,Property Law
LLB Law,Undergraduate,3,2,LAW302,Equity and Trusts
LLB Law,Undergraduate,4,1,LAW401,Commercial Law
LLB Law,Undergraduate,4,2,LAW402,Law Dissertation
BSc Criminology and Security Studies,Undergraduate,1,1,CS101,Introduction to Criminology
BSc Criminology and Security Studies,Undergraduate,1,2,CS102,Security Studies
BSc Criminology and Security Studies,Undergraduate,2,1,CS201,Crime Analysis
BSc Criminology and Security Studies,Undergraduate,2,2,CS202,Criminal Law
BSc Criminology and Security Studies,Undergraduate,3,1,CS301,Forensic Science
BSc Criminology and Security Studies,Undergraduate,3,2,CS302,Counterterrorism
BSc Criminology and Security Studies,Undergraduate,4,1,CS401,Research Methods
BSc Criminology and Security Studies,Undergraduate,4,2,CS402,Security Project
BSc Education (Mathematics),Undergraduate,1,1,EDM101,Foundations of Education
BSc Education (Mathematics),Undergraduate,1,2,EDM102,Mathematics I
BSc Education (Mathematics),Undergraduate,2,1,EDM201,Mathematics II
BSc Education (Mathematics),Undergraduate,2,2,EDM202,Educational Psychology
BSc Education (Mathematics),Undergraduate,3,1,EDM301,Teaching Methods in Mathematics
BSc Education (Mathematics),Undergraduate,3,2,EDM302,Mathematics Curriculum Development
BSc Education (Mathematics),Undergraduate,4,1,EDM401,Teaching Practicum I
BSc Education (Mathematics),Undergraduate,4,2,EDM402,Teaching Practicum II
BSc Education (Science),Undergraduate,1,1,EDS101,Foundations of Education
BSc Education (Science),Undergraduate,1,2,EDS102,General Science I
BSc Education (Science),Undergraduate,2,1,EDS201,General Science II
BSc Education (Science),Undergraduate,2,2,EDS202,Educational Psychology
BSc Education (Science),Undergraduate,3,1,EDS301,Teaching Methods in Science
BSc Education (Science),Undergraduate,3,2,EDS302,Science Curriculum Development
BSc Education (Science),Undergraduate,4,1,EDS401,Teaching Practicum I
BSc Education (Science),Undergraduate,4,2,EDS402,Teaching Practicum II"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import psycopg2

    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return

    # psycopg2 needs postgresql:// not postgres://
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Parse CSV
    rows = list(csv.DictReader(io.StringIO(CSV_DATA.strip())))

    # Collect unique programmes and their courses
    programmes_courses = {}  # prog_name -> list of (year, semester, code, course_name)
    for row in rows:
        prog = row['Programme'].strip()
        if prog not in programmes_courses:
            programmes_courses[prog] = []
        programmes_courses[prog].append((
            int(row['Year']),
            int(row['Semester']),
            row['Course Code'].strip(),
            row['Course Name'].strip()
        ))

    inserted_prog = 0
    inserted_subj = 0
    skipped_prog = 0
    skipped_subj = 0

    # Sort programmes by enrollment desc for order
    sorted_progs = sorted(
        programmes_courses.keys(),
        key=lambda p: -ENROLLMENT.get(p, 0)
    )

    for order_idx, prog_name in enumerate(sorted_progs):
        courses = programmes_courses[prog_name]
        faculty = FACULTY_MAP.get(prog_name, 'Other')
        icon = PROGRAMME_ICONS.get(faculty, 'graduation-cap')
        color = FACULTY_COLORS.get(faculty, '#8b5cf6')
        slug = slugify(prog_name)

        # Insert or skip programme
        cur.execute("SELECT id FROM programme WHERE name = %s", (prog_name,))
        existing = cur.fetchone()
        if existing:
            prog_id = existing[0]
            # Update faculty if missing
            cur.execute("UPDATE programme SET faculty = %s WHERE id = %s AND (faculty IS NULL OR faculty = '')",
                        (faculty, prog_id))
            skipped_prog += 1
        else:
            cur.execute(
                """INSERT INTO programme (name, slug, icon, color, "order", is_active, faculty, created_at)
                   VALUES (%s, %s, %s, %s, %s, true, %s, NOW()) RETURNING id""",
                (prog_name, slug, icon, color, order_idx, faculty)
            )
            prog_id = cur.fetchone()[0]
            inserted_prog += 1

        # Insert subjects (one per unique course name in this programme)
        seen_in_prog = {}
        for year, semester, code, course_name in courses:
            # Subject name = "CODE: Course Name" for uniqueness across programmes
            subj_name = f"{code}: {course_name}"
            subj_slug = slugify(subj_name)
            subj_order = (year - 1) * 20 + (semester - 1) * 10

            if subj_name in seen_in_prog:
                continue
            seen_in_prog[subj_name] = True

            cur.execute("SELECT id FROM subject WHERE name = %s", (subj_name,))
            if cur.fetchone():
                skipped_subj += 1
                continue

            cur.execute(
                """INSERT INTO subject (name, slug, icon, color, "order", is_active, programme_id, post_count, created_at)
                   VALUES (%s, %s, %s, %s, %s, true, %s, 0, NOW())""",
                (subj_name, subj_slug, 'book', color, subj_order, prog_id)
            )
            inserted_subj += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Done!")
    print(f"   Programmes  — inserted: {inserted_prog}, skipped (already exist): {skipped_prog}")
    print(f"   Subjects    — inserted: {inserted_subj}, skipped (already exist): {skipped_subj}")


if __name__ == '__main__':
    main()