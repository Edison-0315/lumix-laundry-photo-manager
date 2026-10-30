import time
from pianji.jobs import JobManager

def wait(manager,ident):
    for _ in range(200):
        s=manager.get_task(ident)
        if s['status'] in ('succeeded','partial','failed','cancelled'): return s
        time.sleep(.01)
    raise AssertionError('job did not terminate')

def test_cancel_and_exception_do_not_kill_queue():
    jobs=JobManager()
    def long(cancel,progress):
        while not cancel(): time.sleep(.002)
        return {'cancelled':True}
    ident=jobs.submit('scan',long); jobs.cancel_task(ident)
    assert wait(jobs,ident)['status']=='cancelled'
    bad=jobs.submit('bad',lambda c,p:1/0)
    assert wait(jobs,bad)['status']=='failed'
    good=jobs.submit('good',lambda c,p:{'answer':42})
    assert wait(jobs,good)['result']['answer']==42
    jobs.close()
