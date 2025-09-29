from flask import Flask, render_template, request, redirect
import openstack_utils as utils

app = Flask(__name__)
conn = utils.get_connection()
PREFIX = "demo"

@app.route("/")
def index():
    servers = list(conn.compute.servers())
    return render_template("index.html", servers=servers)

@app.route("/deploy", methods=["POST"])
def deploy():
    n = int(request.form["num_vm"])
    utils.cleanup(conn, PREFIX)
    net, subnet, router = utils.create_infra(conn, PREFIX)
    for i in range(n):
        utils.create_server(conn, f"{PREFIX}-vm{i+1}", net)
    return redirect("/")

@app.route("/scale", methods=["POST"])
def scale():
    n = int(request.form["num_vm"])
    servers = [s for s in conn.compute.servers() if s.name.startswith(PREFIX)]
    diff = n - len(servers)
    net = conn.network.find_network(f"{PREFIX}-net")
    if diff > 0:
        for i in range(diff):
            utils.create_server(conn, f"{PREFIX}-vm{len(servers)+i+1}", net)
    elif diff < 0:
        for s in servers[diff:]:
            conn.compute.delete_server(s.id, force=True)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
