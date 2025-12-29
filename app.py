from flask import Flask, render_template, request, redirect, session
from azure.storage.blob import BlobServiceClient
from PIL import Image
from datetime import datetime
import json, os, uuid, io

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "simplekey")

AZURE_ACCOUNT = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_KEY = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
AZURE_CONTAINER = os.environ.get("AZURE_STORAGE_CONTAINER_NAME")

blob_service = BlobServiceClient(
    account_url=f"https://{AZURE_ACCOUNT}.blob.core.windows.net",
    credential=AZURE_KEY
)
container = blob_service.get_container_client(AZURE_CONTAINER)

def load_json(file):
    if not os.path.exists(file):
        return []
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def resize_for_feed(img):
    w, h = img.size
    if abs(w - h) < 50:
        target = (1080, 1080)
    elif h > w:
        target = (1080, 1350)
    else:
        target = (1080, 566)
    img.thumbnail(target)
    return img

@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        for u in load_json("users.json"):
            if u["email"]==request.form["email"] and u["password"]==request.form["password"]:
                session["user"]=u["email"]
                return redirect("/home")
    return render_template("login.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        users = load_json("users.json")
        users.append({"email":request.form["email"],"password":request.form["password"]})
        save_json("users.json", users)
        return redirect("/")
    return render_template("signup.html")

@app.route("/home")
def home():
    if "user" not in session:
        return redirect("/")
    posts = sorted(load_json("posts.json"), key=lambda x:x.get("timestamp",""), reverse=True)
    return render_template("home.html", posts=posts)

@app.route("/upload", methods=["GET","POST"])
def upload():
    if "user" not in session:
        return redirect("/")
    if request.method=="POST":
        file = request.files["photo"]
        img = Image.open(file).convert("RGB")
        img = resize_for_feed(img)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        name=f"{uuid.uuid4()}.jpg"
        container.upload_blob(name, buf, overwrite=True)
        posts = load_json("posts.json")
        posts.append({
            "image_url": f"https://{AZURE_ACCOUNT}.blob.core.windows.net/{AZURE_CONTAINER}/{name}",
            "user": session["user"],
            "timestamp": datetime.utcnow().isoformat()
        })
        save_json("posts.json", posts)
        return redirect("/home")
    return render_template("upload.html")

@app.route("/profile", methods=["GET","POST"])
def profile():
    if "user" not in session:
        return redirect("/")
    users=load_json("users.json")
    user = next((u for u in users if u["email"]==session["user"]), None)
    if not user:
        return redirect("/logout")
    if request.method=="POST":
        user["title"]=request.form.get("title")
        user["first_name"]=request.form.get("first_name")
        user["last_name"]=request.form.get("last_name")
        user["dob"]=request.form.get("dob")
        if "profile_pic" in request.files and request.files["profile_pic"].filename:
            img = Image.open(request.files["profile_pic"]).convert("RGB")
            img.thumbnail((320,320))
            buf=io.BytesIO()
            img.save(buf,format="JPEG",quality=90)
            buf.seek(0)
            name=f"profile_{uuid.uuid4()}.jpg"
            container.upload_blob(name, buf, overwrite=True)
            user["profile_pic"]=f"https://{AZURE_ACCOUNT}.blob.core.windows.net/{AZURE_CONTAINER}/{name}"
        save_json("users.json", users)
        return redirect("/profile")
    posts = [p for p in load_json("posts.json") if p["user"]==session["user"]]
    return render_template("profile.html", user=user, posts=posts)

@app.route("/settings")
def settings():
    if "user" not in session:
        return redirect("/")
    return render_template("settings.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__=="__main__":
    app.run(debug=True)
