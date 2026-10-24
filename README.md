# FastAPI Full-Stack RBAC Application

A production-ready full-stack web application built with **FastAPI**, **PostgreSQL**, **SQLAlchemy**, and **Vanilla JavaScript/HTML**, featuring secure JWT Authentication and Role-Based Access Control (RBAC).

## 🚀 Features
- **User Authentication**: Secure registration and login using OAuth2 password flow and JWT tokens.
- **Role-Based Access Control (RBAC)**: Restricted access where only users with an `admin` role can access the Admin Dashboard.
- **Database Management**: Robust ORM integration using SQLAlchemy with PostgreSQL.
- **Rate Limiting**: Built-in request limiting using `slowapi` to protect authentication routes.
- **CORS Support**: Configured CORS middleware for smooth frontend-backend communication.

## 🛠️ Tech Stack
- **Backend**: Python, FastAPI, Uvicorn, SQLAlchemy, Pydantic, PyJWT, Passlib (Bcrypt), SlowAPI
- **Database**: PostgreSQL / pgAdmin
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/shrivastavaamancs-sys/my-backend-project.git](https://github.com/shrivastavaamancs-sys/my-backend-project.git)
cd my-backend-project
