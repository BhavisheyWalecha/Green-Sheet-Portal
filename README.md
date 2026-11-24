Every club event in our college needs a "green sheet" signed by a chain of authorities, and right now that sheet walks from desk to desk on paper. This project moves the whole thing online.

A club secretary uploads the sheet as a PDF. The system checks it, then approvers sign it one after another, and each approver picks who signs next. The DSW gives the final approval, the DSW office prints and stamps it, and the club collects it.

Built with: FastAPI and SQLAlchemy (SQLite by default), React with Vite, SMTP for email (Mailpit while developing), and an optional Claude API call for the AI check.

Running it locally

Start the backend (runs at http://localhost:8000, API docs at `/docs`):
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

Then the frontend (runs at http://localhost:5173):
cd frontend
npm install
npm run dev

Demo accounts

Every account uses the password `password123`.

| Role | Email |
| Robotics club secretary | riya.secretary@clubs.college.edu |
| Robotics club joint secretary | karan.joint@clubs.college.edu |
| Cultural club secretary | ananya.secretary@clubs.college.edu |
| Coordinator | arun.kumar@college.edu |
| HoD | hod.cse@college.edu |
| Approver | iyer@college.edu |
| Dean of Student Welfare | dean.sw@college.edu |
| DSW office | dsw.office@college.edu |
| Admin | admin@college.edu |

How a sheet moves

  A[Club uploads PDF and description] --> B{AI check}
  B -- unsafe or unreadable --> X[Blocked, club is told why] --> A
  B -- ok or warnings only --> C[First approver]
  C -- approve, e-sign, pick next --> D[Next approver]
  D -- approve, e-sign, pick next --> E[Dean of Student Welfare]
  E -- final approval and e-sign --> F[DSW office prints and stamps]
  F --> G[Club collects the sheet]
  C & D & E -- request changes --> H[Club edits and resubmits] --> C
  C & D & E -- reject --> R[Rejected]
  A -. revoke before final approval .-> V[Revoked]

Where each requirement lives in the code

| What it does | Where to look |
| Login, roles and a dashboard per role | `security.py`, `main.py` (`can_view`, `list_sheets`), `pages/Dashboard.jsx` |
| Only club secretaries and joint secretaries can submit, and only from a club email | `is_club_user`, `CLUB_EMAIL_DOMAIN` in `config.py` |
| AI summary and malicious-content check | `ai_check.py` (rules always run, Claude is optional) |
| Each approver chooses the next step | `act()` in `main.py`. The club's usual path is only a suggestion (`Club.suggested_path`) |
| Only the Dean can give final approval | `FINALIZER_ROLE` in `config.py` |
| Change requests go back to the same approver | `act()` and `resubmit()` |
| Revoke before final approval | `revoke()` |
| E-signature at every step | `esign.py`: hash-chained signatures, a footer on every page and an approval-trail page |
| Approval path with every approver's name | `components/PathTimeline.jsx` |
| Emails to the club mailbox, cc list and people involved | `mailer.py`, `Club.cc_emails` |
| DSW print, stamp and collect | `/dsw/stamp`, `/dsw/collected`, `DswPanel` |