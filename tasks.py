import time
from asyncio import Task

from celery import Celery
from celery.result import AsyncResult
from kombu import Exchange, Queue
from celery.exceptions import Reject

from celery import bootsteps

default_queue_name = 'default'
default_exchange_name = 'default'
default_routing_key = 'default'
deadletter_suffix = 'deadletter'
deadletter_queue_name = "${0}.{1}".format(default_queue_name, deadletter_suffix)
deadletter_exchange_name = "${0}.{1}".format(default_exchange_name, deadletter_suffix)
deadletter_routing_key = "${0}.{1}".format(default_routing_key, deadletter_suffix)


class DeclareDLXnDLQ(bootsteps.StartStopStep):
    """
    Celery Bootstep to declare the DL exchange and queues before the worker starts
        processing tasks
    """
    requires = {'celery.worker.components:Pool'}

    def start(self, worker):
        app = worker.app

        # Declare DLX and DLQ
        dlx = Exchange(deadletter_exchange_name, type='direct')

        dead_letter_queue = Queue(
            deadletter_queue_name, dlx, routing_key=deadletter_routing_key)

        with worker.app.pool.acquire() as conn:
            dead_letter_queue.bind(conn).declare()


app = Celery(
    'tasks',
    broker='amqp://admin:mypass@localhost:5672//',
    backend='redis://localhost:6379/0')

default_exchange = Exchange(default_exchange_name, type='direct')
default_queue = Queue(
    default_queue_name,
    default_exchange,
    routing_key=default_routing_key,
    queue_arguments={
        'x-dead-letter-exchange': deadletter_exchange_name,
        'x-dead-letter-routing-key': deadletter_routing_key
    })

app.conf.task_queues = (default_queue,)

# Add steps to workers that declare DLX and DLQ if they don't exist
app.steps['worker'].add(DeclareDLXnDLQ)

app.conf.task_default_queue = default_queue_name
app.conf.task_default_exchange = default_exchange_name
app.conf.task_default_routing_key = default_routing_key


class MyTask(Task):
    ignore_result = False


@app.task
def throw():
    raise KeyError

@app.task
def on_chord_error(request, exc, traceback):
    print('Task {0!r} raised error: {1!r}'.format(request.id, exc))

@app.task
def tsum(numbers):
    return sum(numbers)


@app.task
def add(x, y):
    return x + y


@app.task
def multi(x, y):
    return x * y


@app.task
def log_result(x):
    print()


@app.task
def log_error(x):
    return "log_error"


@app.task(bind=True)
def hello(self, a, b):
    time.sleep(1)
    self.update_state(state="PROGRESS", meta={'progress': 50})
    time.sleep(1)
    self.update_state(state="PROGRESS", meta={'progress': 90})
    time.sleep(1)
    return 'hello world: %i' % (a + b)


@app.task
def error_handler(uuid):
    result = AsyncResult(uuid)
    exc = result.get(propagate=False)
    print('Task {0} raised exception: {1!r}\n{2!r}'.format(
        uuid, exc, result.traceback))


if __name__ == '__main__':
    DeclareDLXnDLQ().start()
