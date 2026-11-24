from sqlalchemy import select
from .models import User, Club
from .security import hash_password

PW = "password123"


def seed(db):
    if db.scalar(select(User).limit(1)):
        return
    robotics = Club(name="Robotics Club", email="robotics@clubs.college.edu")
    cultural = Club(name="Cultural Club", email="cultural@clubs.college.edu")
    db.add_all([robotics, cultural])
    db.flush()

    def u(name, email, role, desig="", club=None):
        x = User(name=name, email=email, password_hash=hash_password(PW), role=role, designation=desig, club_id=club.id if club else None)
        db.add(x)
        return x

    u("Portal Admin", "admin@college.edu", "admin", "System Administrator")
    dean = u("Dr. Meera Nair", "dean.sw@college.edu", "dean_sw", "Dean of Student Welfare")
    u("DSW Office", "dsw.office@college.edu", "dsw_office", "DSW Office Staff")
    rc = u("Dr. Arun Kumar", "arun.kumar@college.edu", "approver", "Faculty Coordinator - Robotics Club")
    cc = u("Prof. Sunita Rao", "sunita.rao@college.edu", "approver", "Faculty Coordinator - Cultural Club")
    hod = u("Dr. Vikram Singh", "hod.cse@college.edu", "approver", "Head of Department, CSE")
    ac = u("Prof. R. Iyer", "iyer@college.edu", "approver", "Associate Dean, Student Activities")
    u("Riya Sharma", "riya.secretary@clubs.college.edu", "club_secretary", "Secretary", robotics)
    u("Karan Mehta", "karan.joint@clubs.college.edu", "club_joint_secretary", "Joint Secretary", robotics)
    u("Ananya Das", "ananya.secretary@clubs.college.edu", "club_secretary", "Secretary", cultural)
    u("Rohan Verma", "rohan.joint@clubs.college.edu", "club_joint_secretary", "Joint Secretary", cultural)
    db.flush()
    robotics.suggested_path = [rc.id, hod.id, dean.id]
    cultural.suggested_path = [cc.id, ac.id, dean.id]
    robotics.cc_emails = ["student.council@college.edu"]
    db.commit()
