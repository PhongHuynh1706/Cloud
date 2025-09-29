import sys
import openstack
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLineEdit, QHBoxLayout

class OpenStackApp(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = openstack.connect(cloud="openstack")
        self.initUI()

    def initUI(self):
        self.setWindowTitle("OpenStack Auto Deployment")
        self.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout()

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        btn_cleanup = QPushButton("Cleanup")
        btn_cleanup.clicked.connect(self.cleanup)

        
        deploy_layout = QHBoxLayout()
        self.deploy_input = QLineEdit()
        self.deploy_input.setPlaceholderText("Nhập số mạng...")
        self.deploy_input.setFixedWidth(150)

        btn_deploy = QPushButton("Deploy")
        btn_deploy.clicked.connect(self.deploy)

        deploy_layout.addWidget(btn_deploy)
        deploy_layout.addWidget(self.deploy_input)

        layout.addWidget(self.log)
        layout.addWidget(btn_cleanup)
        layout.addLayout(deploy_layout)

        self.setLayout(layout)


    def log_msg(self, msg):
        self.log.append(msg)
        self.log.ensureCursorVisible()

    def cleanup(self):
        self.log_msg("🔄 Cleaning up resources...")

        # Xóa servers
        for server in self.conn.compute.servers():
            self.log_msg(f"Deleting server: {server.name}")
            self.conn.compute.delete_server(server, ignore_missing=True)

        # Xóa router
        for router in self.conn.network.routers():
            self.log_msg(f"Deleting router: {router.name}")
            # gỡ interface subnet trước
            for port in self.conn.network.ports(device_id=router.id):
                if port.fixed_ips:
                    for ip in port.fixed_ips:
                        try:
                            self.conn.network.remove_interface_from_router(
                                router, subnet_id=ip['subnet_id']
                            )
                            self.log_msg(f"Removed subnet {ip['subnet_id']} from router {router.name}")
                        except Exception as e:
                            self.log_msg(f"⚠️ Failed remove interface: {e}")
            self.conn.network.delete_router(router, ignore_missing=True)

         # Xóa ports (còn sót lại trên networks)
        for port in self.conn.network.ports():
            if port.device_owner == "":  # port không gắn VM/router
                self.log_msg(f"Deleting port: {port.id}")
                try:
                    self.conn.network.delete_port(port, ignore_missing=True)
                except Exception as e:
                    self.log_msg(f"⚠️ Failed delete port {port.id}: {e}")

        # Xóa networks
        for net in self.conn.network.networks():
            if not net.is_router_external:  # giữ lại external network
                self.log_msg(f"Deleting network: {net.name}")
                try:
                    self.conn.network.delete_network(net, ignore_missing=True)
                except Exception as e:
                    self.log_msg(f"⚠️ Failed delete network {net.name}: {e}")

        self.log_msg("✅ Cleanup done!")

    def deploy(self):
        try:
            # Lấy số mạng từ ô nhập
            num_networks = int(self.deploy_input.text())
        except ValueError:
            self.log_msg("❌ Vui lòng nhập số hợp lệ.")
            return
        
        self.log_msg("🚀 Deploying new topology...")

        # External network (tên đúng lấy từ List Networks)
        external_net_name = "Public_Net"
        external_net = self.conn.network.find_network(external_net_name)

        if not external_net:
            self.log_msg(f"❌ External network '{external_net_name}' not found! Kiểm tra lại tên.")
            return

        # Tạo router
        router = self.conn.network.create_router(
            name="router1",
            external_gateway_info={"network_id": external_net.id}
        )
        self.log_msg(f"Created router: {router.name}")
        
        # Tạo nhiều internal networks và 1 VM trong mỗi mạng
        for i in range(1, num_networks + 1):  # ví dụ 2 mạng internal
            net = self.conn.network.create_network(name=f"net{i}")
            subnet = self.conn.network.create_subnet(
                name=f"subnet{i}",
                network_id=net.id,
                ip_version=4,
                cidr=f"10.0.{i}.0/24",
                gateway_ip=f"10.0.{i}.1"
            )
            self.conn.network.add_interface_to_router(router, subnet_id=subnet.id)
            self.log_msg(f"Created network {net.name} with subnet {subnet.cidr}")

            # Tạo port cho VM
            port = self.conn.network.create_port(network_id=net.id, name=f"vm{i}-port")
            self.log_msg(f"Created port {port.name}")

            # Kiểm tra Image
            image_name = "b1d444fe-9376-43ad-a0c6-39877f4d8d0c"
            image = self.conn.compute.find_image(image_name)
            if not image:
                self.log_msg(f"❌ Image '{image_name}' không tồn tại.")
                continue

            # Kiểm tra Flavor
            flavor_name = "d10.xs1"
            flavor = self.conn.compute.find_flavor(flavor_name)
            if not flavor:
                self.log_msg(f"❌ Flavor '{flavor_name}' không tồn tại.")
                continue

            server = self.conn.compute.create_server(
                name=f"vm{i}",
                image_id=image.id,
                flavor_id=flavor.id,
                networks=[{"port": port.id}]
            )
            self.conn.compute.wait_for_server(server)
            self.log_msg(f"VM {server.name} is active!")

        self.log_msg("✅ Deployment completed!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpenStackApp()
    window.show()
    sys.exit(app.exec_())
