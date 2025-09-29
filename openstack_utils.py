import openstack

def get_connection():
    return openstack.connect(cloud="openstack")

def cleanup(conn, prefix="test"):
    # Xóa server
    for server in conn.compute.servers():
        if server.name.startswith(prefix):
            conn.compute.delete_server(server.id, force=True)
            print(f"Deleted server {server.name}")

    # Xóa router (trước tiên phải gỡ interface)
    for r in conn.network.routers():
        if r.name.startswith(prefix):
            # detach tất cả subnet đang gắn vào router
            for port in conn.network.ports(device_id=r.id):
                try:
                    conn.network.remove_interface_from_router(r, subnet_id=port.fixed_ips[0]['subnet_id'])
                    print(f"Detached subnet {port.fixed_ips[0]['subnet_id']} from router {r.name}")
                except Exception as e:
                    print(f"[WARN] Cannot detach interface: {e}")
            conn.network.delete_router(r.id, ignore_missing=True)
            print(f"Deleted router {r.name}")

    # Xóa subnet
    for s in conn.network.subnets():
        if s.name.startswith(prefix):
            conn.network.delete_subnet(s.id, ignore_missing=True)
            print(f"Deleted subnet {s.name}")

    # Xóa network
    for net in conn.network.networks():
        if net.name.startswith(prefix):
            conn.network.delete_network(net.id, ignore_missing=True)
            print(f"Deleted network {net.name}")

def create_infra(conn, prefix="demo"):
    # Network
    net = conn.network.create_network(name=f"{prefix}-net")
    subnet = conn.network.create_subnet(
        name=f"{prefix}-subnet",
        network_id=net.id,
        ip_version="4",
        cidr="192.168.100.0/24",
        gateway_ip="192.168.100.1"
    )
    router = conn.network.create_router(
        name=f"{prefix}-router",
        external_gateway_info={"network_id": get_external_network(conn).id}
    )
    conn.network.add_interface_to_router(router, subnet_id=subnet.id)
    return net, subnet, router

def get_external_network(conn):
    for net in conn.network.networks():
        if net.is_router_external:
            return net
    raise Exception("No external network found")

def create_server(conn, name, net, image_name="Ubuntu 22.04", flavor_name="m1.small"):
    image = conn.compute.find_image(image_name)
    flavor = conn.compute.find_flavor(flavor_name)
    network = {"uuid": net.id}
    userdata = """#!/bin/bash
apt update -y
apt install -y apache2
echo "<h1>Group: 01 - VM IP: $(hostname -I)</h1>" > /var/www/html/index.html
systemctl enable apache2
systemctl restart apache2
"""
    server = conn.compute.create_server(
        name=name,
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[network],
        user_data=userdata
    )
    server = conn.compute.wait_for_server(server)
    return server
