APP = docker compose -f application-level/docker-compose.yml
PLATFORM = docker compose -f platform-provided/docker-compose.yml

.PHONY: application-up application-demo application-stop-instance application-start-instance application-down \
        platform-up platform-demo platform-stop-instance platform-start-instance platform-down clean

application-up:
	$(APP) up --build -d consul order-1 order-2 order-3

application-demo:
	$(APP) --profile tools run --rm --no-deps client

application-stop-instance:
	$(APP) stop order-2

application-start-instance:
	$(APP) start order-2

application-down:
	$(APP) down -v --remove-orphans

platform-up:
	$(PLATFORM) up --build -d consul registrar nginx-router order-1 order-2 order-3

platform-demo:
	$(PLATFORM) --profile tools run --rm --no-deps demo-client

platform-stop-instance:
	$(PLATFORM) stop order-2

platform-start-instance:
	$(PLATFORM) start order-2

platform-down:
	$(PLATFORM) down -v --remove-orphans

clean:
	-$(APP) down -v --remove-orphans
	-$(PLATFORM) down -v --remove-orphans
