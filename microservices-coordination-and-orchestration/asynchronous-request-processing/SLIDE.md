<!-- header: <i class="fas fa-sync-alt"></i> Improving Availability with Asynchronous Request Processing -->

<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 18px;">

<div style="flex: 0 0 53%; padding-right: 8px; margin-top: 10px;">

> **#### <i class="fas fa-clock"></i> Finish Processing After the Response**
> - **Order Service** creates an order in `PENDING` state and returns **`202 Accepted`**.
> - **Consumer** and **Restaurant Services** validate independently through RabbitMQ.
> - The client can query the order's status without waiting for the validations.

> **#### <i class="fas fa-check-circle"></i> Asynchronous Completion**
> - Order Service processes both results and sets `VALIDATED` only when **both checks succeed**.
> - **Trade-off:** Database updates and message publishing are not automatically atomic — motivating the **Outbox Pattern**.
> - <i class="fas fa-flask"></i> **See example:** [Asynchronous Order Processing](https://github.com/saverioieva/information-systems-design-big-data-examples/tree/main/microservices-coordination-and-orchestration/asynchronous-request-processing)

</div>

<div style="flex: 0 0 44%; margin-top: 8px; text-align: center;">
    <img style="max-width: 100%; height: auto;" src="assets/img/lesson4/asynchronous-request-processing.png" />
</div>
</div>

---
