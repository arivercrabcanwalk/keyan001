"""Java48-compatible draws and strict recorded-choice replay, not a policy."""
class JavaRandom:
    def __init__(self,seed=0):self.seed=(seed^0x5DEECE66D)&((1<<48)-1);self.draws=[]
    def bits(self,n):self.seed=(self.seed*0x5DEECE66D+0xB)&((1<<48)-1);return self.seed>>(48-n)
    def randrange(self,bound):
        if bound<=0:raise ValueError('positive bound required')
        if bound & -bound == bound:value=(bound*self.bits(31))>>31
        else:
            while True:
                bits=self.bits(31);value=bits%bound
                if bits-value+(bound-1)<(1<<31):break
        self.draws.append({'kind':'int','bound':bound,'value':value});return value
    def random(self):
        value=((self.bits(26)<<27)+self.bits(27))/float(1<<53)
        self.draws.append({'kind':'double','value':value});return value
    def choice(self,items):return items[self.randrange(len(items))]
    def choices(self,items,weights,k=1):
        out=[]
        for _ in range(k):
            draw=self.random()*sum(weights);cumulative=0.0
            for item,weight in zip(items,weights):
                cumulative+=weight
                if draw<=cumulative:break
            out.append(item)
        return out

class ReplayChoices:
    def __init__(self,draws):self.draws=list(draws);self.position=0
    def take(self,kind,bound=None):
        if self.position>=len(self.draws):raise AssertionError('random tape exhausted')
        item=self.draws[self.position];self.position+=1
        assert item['kind']==kind,(self.position,item,kind)
        if bound is not None:assert item['bound']==bound,('draw_bound',self.position,item['bound'],bound)
        return item['value']
    def randrange(self,bound):return self.take('int',bound)
    def random(self):return self.take('double')
    def choice(self,items):return items[self.randrange(len(items))]
    def choices(self,items,weights,k=1):
        return JavaRandom.choices(self,items,weights,k)
