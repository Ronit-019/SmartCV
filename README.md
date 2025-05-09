

# SmartCV – A Skill Assessment and Job Recommendation Platform for Students and Companies


SmartCV is a Flask-based web application that streamlines the screening and job application process. It provides role-based dashboards for students, companies, and administrators, with features including coding assessments, CV uploads, skill-based job matching, and an admin control panel.


 🚀 Features


 🧑‍🎓 Student Portal


 Register with education, skills, and CV

 View skill-matched job recommendations

 Apply for jobs directly

 Attempt skill-based coding tests (Python, Java, JS, C++, etc.)

 Track application status

 View and edit personal profile and scores


 🏢 Company Portal


 Post jobs with required skills and score thresholds

 View applicants per job posting

 Update application status (e.g., "Under Review", "Shortlisted")


 👨‍💼 Admin Portal


 Full access to user database

 View all jobs and applications across the platform


 🧪 Coding Test Engine


 Integrated with [Piston API](https://github.com/engineer-man/piston) to compile and execute code in real-time

 Auto-evaluation with scoring and feedback

 Tracks test scores per user and skill


 🛠️ Tech Stack


 Backend: Flask, SQLAlchemy

 Frontend: HTML, Jinja Templates

 Database: SQLite

 External APIs: [Piston API](https://emkc.org/api/v2/piston/execute) for code execution

 Email Service: Flask-Mail (optional for extension)

 Timezone Handling: `pytz`


 📂 Project Structure


```

smartcv/

│

├── static/uploads/cv/      Uploaded CV files

├── templates/              HTML templates

├── smartcv.db              SQLite DB

├── app.py                  Main Flask application

└── README.md               Project readme

```


 🔧 Setup Instructions


1. Clone the repository


   ```bash

   git clone https://github.com/yourusername/smartcv.git

   cd smartcv

   ```


2. Install dependencies


   ```bash

   pip install -r requirements.txt

   ```


3. Run the application


   ```bash

   python app.py

   ```


4. Access locally


   ```

   http://127.0.0.1:5000/

   ```


 📝 User Roles


| Role    | Access Level                                    |

| ------- | ----------------------------------------------- |

| Student | Apply for jobs, take coding tests, view profile |

| Company | Post jobs, view applicants, manage applications |

| Admin   | View all users, jobs, and applications          |


 📌 Default Admin Login


```txt

Email: admin@gmail.com

Password: admin123

```


 🛡️ Security Notes


 Passwords are stored in plaintext for simplicity. Use hashed passwords (e.g., with bcrypt) for production.

 Input validation and CSRF protection are minimal. Integrate Flask-WTF or similar for robust protection.


 💡 Future Improvements


 Email notifications on application updates

 Resume parsing for skill extraction

 Interview scheduling and feedback loop

 User analytics dashboard


 📃 License


This project is under the MIT License. Feel free to use and modify for academic or commercial purposes.


👨‍💻 Developed By


\Ronit Rajput – ICT Engineer, 3rd Year

Feel free to connect on https://www.linkedin.com/in/ronit-rajput-973602278 or reach out via email.


