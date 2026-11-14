"""UPnP port mapping against a fake router (no network, never the real one)."""
import http.server
import re
import threading
import time
import unittest

from draco import upnp

DESC = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0"><device>
 <deviceType>urn:schemas-upnp-org:device:InternetGatewayDevice:1</deviceType>
 <deviceList><device><deviceList><device>
  <serviceList><service>
   <serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType>
   <controlURL>/ctl/IPConn</controlURL>
  </service></serviceList>
 </device></deviceList></device></deviceList>
</device></root>"""


class Router(http.server.BaseHTTPRequestHandler):
    calls = []
    permanent_only = False

    def log_message(self, *a):
        pass

    def do_GET(self):
        body = DESC.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"])).decode()
        action = self.headers["SOAPAction"].strip('"').split("#")[1]
        fields = dict(re.findall(r"<(New\w+)>([^<]*)</New\w+>", data))
        if action == "AddPortMapping" and Router.permanent_only and fields["NewLeaseDuration"] != "0":
            body = b"<s:Envelope><s:Body><s:Fault><detail><UPnPError><errorCode>725</errorCode></UPnPError>" \
                   b"</detail></s:Fault></s:Body></s:Envelope>"
            self.send_response(500)
        else:
            Router.calls.append((action, fields.get("NewExternalPort"), fields.get("NewProtocol"),
                                 fields.get("NewLeaseDuration")))
            body = b"<s:Envelope><s:Body><u:R><NewExternalIPAddress>198.51.100.7</NewExternalIPAddress>" \
                   b"</u:R></s:Body></s:Envelope>"
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class UPnPTests(unittest.TestCase):
    def setUp(self):
        Router.calls, Router.permanent_only = [], False
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Router)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.loc = f"http://127.0.0.1:{self.httpd.server_address[1]}/desc.xml"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def gateway(self):
        return upnp.gateway_from_description(self.loc, DESC)

    def test_description_and_soap(self):
        gw = self.gateway()
        self.assertEqual(gw.control_url, self.loc.replace("/desc.xml", "/ctl/IPConn"))
        self.assertEqual(gw.service, "urn:schemas-upnp-org:service:WANIPConnection:1")
        self.assertEqual(gw.local_ip, "127.0.0.1")
        self.assertEqual(gw.external_ip(), "198.51.100.7")
        gw.add(40001, "TCP")
        gw.delete(40001, "TCP")
        self.assertEqual(Router.calls[1:], [("AddPortMapping", "40001", "TCP", "3600"),
                                            ("DeletePortMapping", "40001", "TCP", None)])

    def test_permanent_lease_fallback(self):
        Router.permanent_only = True
        self.gateway().add(40002, "UDP")
        self.assertEqual(Router.calls, [("AddPortMapping", "40002", "UDP", "0")])

    def test_no_wan_service(self):
        self.assertIsNone(upnp.gateway_from_description(self.loc, "<root><device/></root>"))

    def test_mapper_holds_and_releases(self):
        m = upnp.PortMapper(finder=self.gateway)

        def wait_for(n):
            end = time.monotonic() + 5
            while len(Router.calls) < n and time.monotonic() < end:
                time.sleep(0.05)
        a, b = [(40010, "TCP"), (40010, "UDP")], [(40011, "TCP"), (40011, "UDP")]
        m.hold(a)
        wait_for(2)
        m.hold(b)
        wait_for(4)
        self.assertEqual(sorted(c[:3] for c in Router.calls),
                         sorted(("AddPortMapping", str(p), proto) for p, proto in a + b))
        self.assertEqual(m.status, "open")
        Router.calls.clear()
        m.release(a)
        wait_for(2)
        self.assertEqual(sorted(c[:3] for c in Router.calls),
                         sorted(("DeletePortMapping", str(p), proto) for p, proto in a))
        Router.calls.clear()
        m.close()                                  # quitting removes what is left
        self.assertEqual(sorted(c[:3] for c in Router.calls),
                         sorted(("DeletePortMapping", str(p), proto) for p, proto in b))

    def test_mapper_without_router(self):
        m = upnp.PortMapper(finder=lambda: None)
        m.hold([(40020, "TCP")])
        end = time.monotonic() + 3
        while m.status != "no router" and time.monotonic() < end:
            time.sleep(0.05)
        self.assertEqual(m.status, "no router")
        m.close()


if __name__ == "__main__":
    unittest.main()
