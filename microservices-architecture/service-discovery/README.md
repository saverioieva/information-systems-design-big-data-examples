# Service Discovery — Application-Level vs Platform-Provided

This lab demonstrates how microservices can locate **dynamically changing service instances** without hardcoding container IP addresses.

It revisits the previous Consul-based discovery example and restructures it to match the terminology and diagrams used in the course slides:

1. **Application-level discovery**
   - self-registration;
   - client-side discovery;
   - client-side instance selection/load balancing.
2. **Platform-provided discovery**
   - third-party registration;
   - server-side discovery;
   - platform-side load balancing.

The lab is intentionally **Docker-first**. The host only needs Docker and Docker Compose.

> **Scope:** this example focuses on service registration, lookup, and routing. It intentionally keeps the Order Service itself simple instead of introducing Hexagonal Architecture again. The architectural concern under study is **service location**, not the internal design of the service.

---

## 1. The common problem: dynamic service locations

Three instances of the same logical service run at the same time:

```text
order-service
   |
   +-- order-1   dynamic container IP
   +-- order-2   dynamic container IP
   +-- order-3   dynamic container IP
```

Container addresses can change after restarts, failures, scaling, or redeployments. A client should therefore depend on a **logical service identity** such as:

```text
order-service
```

rather than on addresses such as:

```text
172.20.0.4:8000
172.20.0.5:8000
172.20.0.6:8000
```

Both variants use **Consul** as the service registry, but responsibility for registration and instance selection is deliberately different.

---

## 2. Project structure

```text
service-discovery/
├── common/
│   └── order-service/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── main.py
├── application-level/
│   ├── client/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── client.py
│   └── docker-compose.yml
├── platform-provided/
│   ├── nginx/
│   │   └── nginx.conf
│   ├── registrar/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── registrar.py
│   ├── demo-client/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── demo.py
│   └── docker-compose.yml
├── Makefile
└── README.md
```

The same FastAPI `order-service` image is reused in both scenarios. The difference is **who registers instances and who chooses the target instance**.

---

# Part A — Application-Level Service Discovery

## 3. Architecture

```text
                    self-registration
       +------------------------------------------+
       |                    |                     |
       v                    v                     v
   Order 1              Order 2               Order 3
       |                    |                     |
       +--------------------+---------------------+
                            |
                            v
                     Service Registry
                         (Consul)
                            ^
                            |
                   query(order-service)
                            |
                            v
                     Service Client
                            |
                   selects one instance
                            |
                            v
                     HTTP request directly
```

There are two application-level responsibilities.

### Self-registration

Each Order Service instance registers itself with Consul during startup:

```text
Order instance
     |
     | PUT /v1/agent/service/register
     v
   Consul
```

The registration contains:

- logical service name: `order-service`;
- current container IP address;
- service port `8000`;
- health-check endpoint `/health`;
- an instance identifier such as `order-1`.

The service also deregisters itself during a graceful shutdown. If it disappears abruptly, Consul health checks prevent unhealthy instances from being returned to the client.

### Client-side discovery

The client queries Consul for **healthy** `order-service` instances:

```text
Client
  |
  | query order-service
  v
Consul
  |
  | [order-1, order-2, order-3]
  v
Client
  |
  | choose instance
  v
Order instance
```

The client performs a simple round-robin selection itself. Therefore both discovery and load-balancing logic are visible in application code.

---

## 4. Run application-level discovery

Start Consul and the three self-registering Order Service instances:

```bash
make application-up
```

Open the Consul UI:

```text
http://localhost:8500
```

You should see one logical service named:

```text
order-service
```

with three healthy instances.

Run the Dockerized client:

```bash
make application-demo
```

Typical output:

```text
Application-level discovery demo
Client queries Consul and selects the target instance itself.

Discovered 3 healthy instance(s) for 'order-service':
  - order-1  172.x.x.x:8000
  - order-2  172.x.x.x:8000
  - order-3  172.x.x.x:8000

01. selected order-1  -> HTTP 200, response instance=order-1
02. selected order-2  -> HTTP 200, response instance=order-2
03. selected order-3  -> HTTP 200, response instance=order-3
...
```

The important point is that the client first discovers the current addresses and then sends HTTP requests **directly to the selected instances**.

---

## 5. Observe a dynamic membership change

Stop one instance:

```bash
make application-stop-instance
```

Wait a few seconds for the health check, then run:

```bash
make application-demo
```

The client should now discover only the healthy instances.

Restart the instance:

```bash
make application-start-instance
```

and run the demo again.

This demonstrates why the client cannot safely cache a static IP list forever.

Stop the scenario:

```bash
make application-down
```

---

# Part B — Platform-Provided Service Discovery

## 6. Architecture

In this variant, the Order Service instances do **not** register themselves and the client does **not** query Consul.

```text
                         Deployment platform

 Order 1 ----+                                    +--> Order 1
 Order 2 ----+--> Registrar --> Consul DNS        +--> Order 2
 Order 3 ----+                    ^                +--> Order 3
                                 |                    ^
                                 | DNS lookup         |
                                 |                    | selected request
                              Nginx ------------------+
                         platform router
                                 ^
                                 |
                        logical service request
                                 |
                               Client
```

The responsibilities are separated as follows:

```text
Registrar         -> observes instances and updates the registry
Consul            -> stores locations and exposes them through DNS
Nginx             -> resolves the logical service and load balances requests
Client            -> calls only one stable router endpoint
```

### Third-party registration

The lab includes a small `registrar` container that watches Docker through the read-only Docker socket.

Order Service containers are marked with discovery labels. The registrar observes those containers and registers/deregisters them in Consul:

```text
Docker runtime
     |
     | observed by
     v
Registrar
     |
     | register / deregister
     v
Consul
```

This makes the **third-party registration** responsibility explicit without placing Consul code inside the Order Service.

> The registrar is teaching infrastructure. Mounting the Docker socket is acceptable for this local lab but should not be interpreted as a general production recommendation.

### Server-side discovery with Consul DNS and Nginx

The client sends every request to one stable Nginx endpoint:

```text
Client
   |
   | GET /orders/1001
   v
Nginx
   |
   | DNS query: order-service.service.consul
   v
Consul DNS
   |
   | healthy instance addresses
   v
Nginx
   |
   | select / load balance
   v
Order instance
```

Nginx therefore owns **server-side discovery and request routing**. The client never receives individual service addresses.

The relevant Nginx configuration is intentionally small:

```nginx
resolver consul:8600 valid=2s ipv6=off;

upstream order_service {
    zone order_service 64k;
    server order-service.service.consul:8000 resolve;
}
```

`order-service.service.consul` is the logical DNS name exposed by Consul for the registered service. The `resolve` parameter makes Nginx re-resolve the upstream dynamically, so changes in the registry can be reflected without hardcoding container addresses.

> **Important:** the Service Registry stores location metadata. It does not carry the business request. Nginx queries Consul DNS for available addresses and then forwards the HTTP request directly to the selected Order Service instance.

---

## 7. Run platform-provided discovery

Start Consul, the registrar, Nginx, and the three Order Service instances:

```bash
make platform-up
```

Useful endpoints:

| Component | URL |
|---|---|
| Consul UI | `http://localhost:8500` |
| Nginx logical endpoint | `http://localhost:8080` |
| Nginx health endpoint | `http://localhost:8080/router-health` |

Run the Dockerized client:

```bash
make platform-demo
```

Typical output:

```text
Platform-provided discovery demo
Client calls one logical endpoint; Nginx resolves the service through Consul DNS and load balances across healthy instances.

01. HTTP 200 -> served by order-1
02. HTTP 200 -> served by order-2
03. HTTP 200 -> served by order-3
...
```

The client always calls the same Nginx endpoint. It does not query Consul and does not select an instance itself.

You can also call the router from the host:

```bash
curl -s http://localhost:8080/orders/1001
```

Repeat the command to observe requests being served by different healthy instances.

---

## 8. Observe third-party registration and routing changes

Follow the registrar logs:

```bash
docker compose -f platform-provided/docker-compose.yml logs -f registrar
```

You should see registrations such as:

```text
[register] order-service-order-1 -> 172.x.x.x:8000
[register] order-service-order-2 -> 172.x.x.x:8000
[register] order-service-order-3 -> 172.x.x.x:8000
```

Inspect the service in the Consul UI at:

```text
http://localhost:8500
```

Now stop one instance:

```bash
make platform-stop-instance
```

The registrar observes the change and removes that instance from Consul. Consul DNS then exposes only the remaining healthy instances and Nginx refreshes its upstream addresses.

Run:

```bash
make platform-demo
```

The client still calls the same endpoint, while requests are routed only to the remaining instances.

Restart the instance:

```bash
make platform-start-instance
```

Run the demo again to observe the instance returning to the routing pool.

Stop the scenario:

```bash
make platform-down
```

---

## 9. Application-level vs platform-provided discovery

| Concern | Application-level | Platform-provided |
|---|---|---|
| Registration | Service instance | Registrar / platform |
| Registry | Consul | Consul |
| Discovery interface | Consul HTTP API | Consul DNS |
| Who queries the registry? | Client | Nginx |
| Who selects the instance? | Client | Nginx |
| Load balancing | Client-side | Server-side |
| Does client know instance addresses? | Yes | No |
| Service contains registration code? | Yes | No |
| Router required? | No | Yes |

The two request paths are therefore fundamentally different:

```text
Application-level
-----------------
Client -> Consul -> list of instances
Client ----------------------> selected instance

Platform-provided
-----------------
Client -> Nginx
          Nginx -> Consul DNS -> list of instances
          Nginx ----------------> selected instance
```

The key distinction is **where discovery responsibility lives**.

---

## 10. Relation to the previous example

The earlier course material already used a registry plus a reverse proxy/load balancer. This version keeps the same idea but makes the responsibilities explicit and aligns them with the terminology used in the slides:

```text
Consul     -> Service Registry + DNS discovery interface
Registrar  -> Third-party registration
Nginx      -> Platform Router + server-side load balancing
FastAPI    -> replicated Order Service
```

Compared with the older example:

- the target is a small **real FastAPI Order Service** that reports which instance handled the request;
- the application-level variant uses **actual self-registration** and an explicit client-side discovery client;
- the platform-provided variant uses a transparent **third-party registrar** instead of registration code in the service;
- **Nginx** acts as the platform router and dynamically resolves `order-service.service.consul` through Consul DNS;
- both flows are Docker-first and use finite, reproducible demo commands.

---

## 11. Suggested classroom sequence

```text
1. Start with three Order Service instances
            ↓
2. Observe dynamic instance addresses in Consul
            ↓
3. Application-level:
   instance self-registration
            ↓
   client queries Consul
            ↓
   client selects target
            ↓
4. Stop/restart one instance
            ↓
5. Platform-provided:
   registrar observes instances
            ↓
   registrar updates Consul
            ↓
   Nginx resolves order-service.service.consul
            ↓
   Nginx selects + forwards
            ↓
6. Compare where discovery responsibility lives
```

The key question is not whether a registry exists, but **which component owns registration, lookup, instance selection, and routing**.
