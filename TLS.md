# make CA
 - openssl genrsa -out ca.key 4096
 - openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt

# make certificat
 - openssl genrsa -out server.key 2048
 - openssl req -new -key server.key -out server.csr -addext "subjectAltName=IP:127.0.0.1"

# sign the server's request with the CA
 - openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365 -sha256 -extfile <(printf "subjectAltName=IP:127.0.0.1")

## inspect the certificate
 - openssl x509 -in server.crt -text -noout