from tasks import throw
from celery import chord, group
from tasks import add, throw
c = chord([add.s(4, 4), throw.s(), add.s(8, 8)])

