/* Round-6 native kernel: exact-semantics TSALNS hot path.
 *
 * Every floating-point expression keeps the operand order and association of
 * lrphsd/fidelity_ops_v5.py.  No -ffast-math, no FMA contraction, no
 * reassociation: the build uses -ffp-contract=off.
 *
 * The C side owns four solution slots and the JavaRandom stream used by the
 * destroy operators.  Python keeps the ALNS control flow (operator choice,
 * acceptance, adaptive weights, temperature, budget).
 *
 * Coverage is precomputed in Python with math.hypot (the same expression the
 * independent evaluator uses) and passed in as a [3][NST*NT] byte table, so the
 * kernel never has to reproduce CPython's hypot rounding.
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define MAXST 64
#define MAXDR 2
#define MAXSLOT 4
#define MAXN 4096
#define RANKCAP (MAXN + 4096)
#define MASK48 ((1ULL << 48) - 1)

typedef struct {
    int ntrips;
    int total;
    int cap;      /* capacity of start[] in ints */
    int *start;
    int *nodes;
} Drone;

typedef struct {
    int kind;
    Drone d[MAXDR];
} Station;

typedef struct {
    int nst;
    Station st[MAXST];
} Sol;

static int NID, NST, NT;
static double *DIST, *DTAB, *DENG, *SVC, *ENGE;
static int *STID, *TIDS, *TIDX;
static double SPEED, FE, TCOST;
static double CAP[3][2], LIM[3], RAD[3];
static unsigned char *COVER;      /* solver semantics: dist <= radius */
static unsigned char *COVERG;     /* evaluator semantics: hypot <= radius+1e-7 */
static int MAXNODES, MAXTRIPS;
static Sol S[MAXSLOT];
static int inited = 0;
static int FAULT = 0;

static int e_si[MAXN], e_di[MAXN], e_ti[MAXN], e_pi[MAXN], e_nid[MAXN];
static double rank_delta[RANKCAP];
static int rank_ti[RANKCAP], rank_pos[RANKCAP];
static double scratch_val[MAXN];
static int scratch_idx[MAXN];
static double cand_score[MAXN], cand_weight[MAXN];
static int cand_idx[MAXN];
static unsigned char remmark[MAXN];
static int rm_out[MAXN];
static signed char cover_cache[MAXN];

static void *xmalloc(size_t n) {
    void *p = malloc(n ? n : 1);
    if (!p) abort();
    return p;
}

static double d_abs(double x) { return x < 0 ? -x : x; }

int r6_fault(void) { return FAULT; }
void r6_clear_fault(void) { FAULT = 0; }

int r6_init(int nid, const double *dist, const double *svc, const double *enge,
            int nst, const int *stid, const double *radii,
            int nt, const int *tids,
            double speed, double fe, double tcost,
            const double *caps, const double *limits,
            const unsigned char *cover, const unsigned char *cover_guard) {
    int i, s, di;
    if (inited) return 0;
    if (nst > MAXST || nt > MAXN - 1 || nid > MAXN - 1) return 0;
    NID = nid; NST = nst; NT = nt;
    SPEED = speed; FE = fe; TCOST = tcost;
    DIST = (double *)xmalloc(sizeof(double) * (size_t)NID * NID);
    DTAB = (double *)xmalloc(sizeof(double) * (size_t)NID * NID);
    DENG = (double *)xmalloc(sizeof(double) * (size_t)NID * NID);
    memcpy(DIST, dist, sizeof(double) * (size_t)NID * NID);
    for (i = 0; i < NID * NID; i++) {
        DTAB[i] = DIST[i] / SPEED;
        DENG[i] = (DIST[i] / SPEED) * FE;
    }
    SVC = (double *)xmalloc(sizeof(double) * NID);
    ENGE = (double *)xmalloc(sizeof(double) * NID);
    memcpy(SVC, svc, sizeof(double) * NID);
    memcpy(ENGE, enge, sizeof(double) * NID);
    STID = (int *)xmalloc(sizeof(int) * NST);
    memcpy(STID, stid, sizeof(int) * NST);
    TIDS = (int *)xmalloc(sizeof(int) * NT);
    memcpy(TIDS, tids, sizeof(int) * NT);
    TIDX = (int *)xmalloc(sizeof(int) * NID);
    for (i = 0; i < NID; i++) TIDX[i] = -1;
    for (i = 0; i < NT; i++) TIDX[TIDS[i]] = i;
    for (i = 0; i < 3; i++) {
        RAD[i] = radii[i]; LIM[i] = limits[i];
        CAP[i][0] = caps[i * 2 + 0]; CAP[i][1] = caps[i * 2 + 1];
    }
    COVER = (unsigned char *)xmalloc((size_t)3 * NST * NT);
    memcpy(COVER, cover, (size_t)3 * NST * NT);
    COVERG = (unsigned char *)xmalloc((size_t)3 * NST * NT);
    memcpy(COVERG, cover_guard, (size_t)3 * NST * NT);
    MAXNODES = NT + 1;
    MAXTRIPS = 4096;  /* empty trips are real insertion candidates and accumulate */
    for (s = 0; s < MAXSLOT; s++) {
        S[s].nst = NST;
        for (i = 0; i < NST; i++) {
            S[s].st[i].kind = 0;
            for (di = 0; di < MAXDR; di++) {
                Drone *d = &S[s].st[i].d[di];
                d->cap = 64;
                d->start = (int *)xmalloc(sizeof(int) * (size_t)(d->cap + 1));
                d->nodes = (int *)xmalloc(sizeof(int) * (size_t)MAXNODES);
                d->ntrips = 0; d->total = 0; d->start[0] = 0;
            }
        }
    }
    inited = 1;
    return 1;
}

void r6_free(void) {
    int s, i, di;
    if (!inited) return;
    for (s = 0; s < MAXSLOT; s++)
        for (i = 0; i < NST; i++)
            for (di = 0; di < MAXDR; di++) {
                free(S[s].st[i].d[di].start);
                free(S[s].st[i].d[di].nodes);
            }
    free(DIST); free(DTAB); free(DENG); free(SVC); free(ENGE);
    free(STID); free(TIDS); free(TIDX); free(COVER); free(COVERG);
    inited = 0;
}

/* ---------- drone primitives ---------- */
static inline int trip_len(const Drone *d, int t) { return d->start[t + 1] - d->start[t]; }

static void drone_reserve(Drone *d, int need) {
    int cap;
    if (need <= d->cap) return;
    cap = d->cap;
    while (cap < need) cap *= 2;
    d->start = (int *)realloc(d->start, sizeof(int) * (size_t)(cap + 1));
    if (!d->start) { FAULT = 2; abort(); }
    d->cap = cap;
}

static void d_insert(Drone *d, int t, int pos, int node) {
    int p, i;
    if (d->total + 1 > MAXNODES) { FAULT = 1; return; }
    p = d->start[t] + pos;
    memmove(d->nodes + p + 1, d->nodes + p, sizeof(int) * (size_t)(d->total - p));
    d->nodes[p] = node;
    for (i = t + 1; i <= d->ntrips; i++) d->start[i]++;
    d->total++;
}

static void d_remove(Drone *d, int t, int pos) {
    int p = d->start[t] + pos, i;
    memmove(d->nodes + p, d->nodes + p + 1, sizeof(int) * (size_t)(d->total - p - 1));
    for (i = t + 1; i <= d->ntrips; i++) d->start[i]--;
    d->total--;
}

static void d_newtrip(Drone *d, int node) {
    int b;
    if (d->total + 1 > MAXNODES) { FAULT = 1; return; }
    drone_reserve(d, d->ntrips + 2);
    b = d->start[d->ntrips];
    d->nodes[b] = node;
    d->start[d->ntrips + 1] = b + 1;
    d->ntrips++;
    d->total++;
}

static void station_clear(Station *st, int kind) {
    int di;
    st->kind = kind;
    for (di = 0; di < MAXDR; di++) {
        st->d[di].ntrips = 0; st->d[di].total = 0; st->d[di].start[0] = 0;
    }
}

/* ---------- path statistics (identical operand order) ---------- */
static double path_time(int si, const int *tr, int n) {
    int depot = STID[si], i, prev, cur;
    double v;
    if (n <= 0) return 0.0;
    prev = tr[0];
    v = DTAB[depot * NID + prev];
    for (i = 1; i < n; i++) {
        cur = tr[i];
        v += DTAB[prev * NID + cur];
        v += SVC[prev];
        prev = cur;
    }
    v += DTAB[prev * NID + depot];
    v += SVC[prev];
    return v;
}

static double path_energy_seg(int si, const int *tr, int n) {
    int depot = STID[si], i, prev, cur;
    double v;
    if (n <= 0) return 0.0;
    prev = tr[0];
    v = DENG[depot * NID + prev];
    for (i = 1; i < n; i++) {
        cur = tr[i];
        v += DENG[prev * NID + cur];
        v += ENGE[prev];
        prev = cur;
    }
    v += DENG[prev * NID + depot];
    v += ENGE[prev];
    return v;
}

static double path_energy_raw(int si, const int *tr, int n) {
    int depot = STID[si], i, prev;
    double total = 0.0, extra = 0.0;
    prev = depot;
    for (i = 0; i < n; i++) { total += DIST[prev * NID + tr[i]]; prev = tr[i]; }
    total += DIST[prev * NID + depot];
    for (i = 0; i < n; i++) extra += ENGE[tr[i]];
    return total / SPEED * FE + extra;
}

/* ---------- slots ---------- */
void r6_clear(int slot) {
    int i;
    for (i = 0; i < NST; i++) station_clear(&S[slot].st[i], 0);
}

void r6_clone(int src, int dst) {
    int s, di;
    Sol *a = &S[dst], *b = &S[src];
    if (a == b) return;
    a->nst = b->nst;
    for (s = 0; s < NST; s++) {
        a->st[s].kind = b->st[s].kind;
        for (di = 0; di < MAXDR; di++) {
            Drone *x = &a->st[s].d[di], *y = &b->st[s].d[di];
            drone_reserve(x, y->ntrips + 1);
            x->ntrips = y->ntrips; x->total = y->total;
            memcpy(x->start, y->start, sizeof(int) * (size_t)(y->ntrips + 1));
            if (y->total) memcpy(x->nodes, y->nodes, sizeof(int) * (size_t)y->total);
        }
    }
}

int r6_set_kind(int slot, int si, int kind) {
    if (slot < 0 || slot >= MAXSLOT || si < 0 || si >= NST || kind < 0 || kind > 2) return 0;
    S[slot].st[si].kind = kind;
    return 1;
}
int r6_get_kind(int slot, int si) { return S[slot].st[si].kind; }

int r6_export_size(int slot) {
    Sol *o;
    if (slot < 0 || slot >= MAXSLOT) return -1;
    o = &S[slot];
    int s, di, t, n = 0;
    for (s = 0; s < NST; s++) {
        n += 1;
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            n += 1;
            for (t = 0; t < d->ntrips; t++) n += 1 + (d->start[t + 1] - d->start[t]);
        }
    }
    return n;
}

int r6_export(int slot, int *types_out, int *buf, int bufsize) {
    Sol *o = &S[slot];
    int s, di, t, n = 0, i;
    for (s = 0; s < NST; s++) {
        types_out[s] = o->st[s].kind;
        if (n + 1 > bufsize) return -1;
        buf[n++] = o->st[s].kind;
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            if (n + 1 > bufsize) return -1;
            buf[n++] = d->ntrips;
            for (t = 0; t < d->ntrips; t++) {
                int len = trip_len(d, t);
                if (n + 1 + len > bufsize) return -1;
                buf[n++] = len;
                for (i = 0; i < len; i++) buf[n++] = d->nodes[d->start[t] + i];
            }
        }
    }
    return n;
}


static int buffer_is_valid(const int *buf, int buflen) {
    int n = 0, s, di, t;
    if (buflen <= 0 || buf == NULL) return 0;
    for (s = 0; s < NST; s++) {
        int kind, nt, total;
        if (n + 1 > buflen) return 0;
        kind = buf[n++];
        if (kind < 0 || kind > 2) return 0;
        for (di = 0; di < MAXDR; di++) {
            if (n + 1 > buflen) return 0;
            nt = buf[n++];
            if (nt < 0 || nt > MAXTRIPS) return 0;
            total = 0;
            for (t = 0; t < nt; t++) {
                int len, k;
                if (n + 1 > buflen) return 0;
                len = buf[n++];
                if (len < 0 || total + len > MAXNODES) return 0;
                for (k = 0; k < len; k++) {
                    int nid;
                    if (n >= buflen) return 0;
                    nid = buf[n++];
                    if (nid < 0 || nid >= NID) return 0;
                }
                total += len;
            }
        }
    }
    return 1;
}

int r6_import(int slot, const int *buf, int buflen) {
    Sol *o;
    int n = 0, s, di, t;
    if (slot < 0 || slot >= MAXSLOT) return 0;
    if (!buffer_is_valid(buf, buflen)) return 0;
    o = &S[slot];
    for (s = 0; s < NST; s++) {
        int kind, nt;
        if (n + 1 > buflen) return 0;
        kind = buf[n++];
        station_clear(&o->st[s], kind);
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            if (n + 1 > buflen) return 0;
            nt = buf[n++];
            if (nt < 0 || nt > MAXTRIPS) return 0;
            for (t = 0; t < nt; t++) {
                int len, k, base;
                if (n + 1 > buflen) return 0;
                len = buf[n++];
                if (len < 0 || d->total + len > MAXNODES) return 0;
                drone_reserve(d, d->ntrips + 2);
                base = d->start[d->ntrips];
                for (k = 0; k < len; k++) {
                    if (n >= buflen) return 0;
                    d->nodes[base + k] = buf[n++];
                }
                d->start[d->ntrips + 1] = base + len;
                d->ntrips++;
                d->total += len;
            }
        }
    }
    return 1;
}

/* ---------- objective / feasibility ---------- */
double r6_cost(int slot) {
    Sol *o = &S[slot];
    int s, di, t;
    double value = 0.0;
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            for (t = 0; t < d->ntrips; t++)
                value += path_time(s, d->nodes + d->start[t], d->start[t + 1] - d->start[t]) * TCOST;
        }
    return value;
}

int r6_valid(int slot, int time_check) {
    Sol *o = &S[slot];
    int s, di, t;
    for (s = 0; s < NST; s++) {
        int kind = o->st[s].kind;
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            if (kind) {
                double cap = CAP[kind][di];
                for (t = 0; t < d->ntrips; t++)
                    if (path_energy_raw(s, d->nodes + d->start[t], d->start[t + 1] - d->start[t]) > cap)
                        return 0;
            }
            if (time_check) {
                double total = 0.0, lim = LIM[kind];
                for (t = 0; t < d->ntrips; t++)
                    total += path_time(s, d->nodes + d->start[t], d->start[t + 1] - d->start[t]);
                if (total > lim) return 0;
            }
        }
    }
    return 1;
}

int r6_complete(int slot) {
    Sol *o = &S[slot];
    static int counts[MAXN];
    int s, di, i, k;
    for (i = 0; i < NT; i++) counts[i] = 0;
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            for (i = 0; i < d->total; i++) {
                int nid = d->nodes[i], ti;
                if (nid < 0 || nid >= NID) return 0;
                ti = TIDX[nid];
                if (ti < 0) return 0;
                counts[ti]++;
            }
        }
    for (k = 0; k < NT; k++) if (counts[k] != 1) return 0;
    return 1;
}

int r6_guard(int slot) {
    /* Mirrors the independent evaluator on the *physical* form: a small station
     * (kind 1) merges storage drone 0 into drone 1 before the checks. */
    Sol *o = &S[slot];
    static int counts[MAXN];
    int s, di, t, i, j, k;
    for (i = 0; i < NT; i++) counts[i] = 0;
    for (s = 0; s < NST; s++) {
        int kind = o->st[s].kind, stid = STID[s];
        if (kind == 0) {
            for (di = 0; di < MAXDR; di++) {
                Drone *d = &o->st[s].d[di];
                for (t = 0; t < d->ntrips; t++) if (d->start[t + 1] > d->start[t]) return 0;
            }
            continue;
        }
        if (kind == 1) {
            double drone_time = 0.0, cap = CAP[1][1], lim = LIM[1];
            for (di = 0; di < MAXDR; di++) {
                Drone *d = &o->st[s].d[di];
                for (t = 0; t < d->ntrips; t++) {
                    int b = d->start[t], e = d->start[t + 1], len = e - b, prev = stid;
                    double length = 0.0, service = 0.0, energy, travel, e2 = 0.0;
                    if (len <= 0) continue;
                    for (j = 0; j < len; j++) {
                        int nid = d->nodes[b + j];
                        int ti = (nid >= 0 && nid < NID) ? TIDX[nid] : -1;
                        if (ti < 0) return 0;
                        counts[ti]++;
                        if (!COVERG[(size_t)kind * NST * NT + (size_t)s * NT + ti]) return 0;
                        length += DIST[(size_t)prev * NID + nid];
                        prev = nid;
                    }
                    length += DIST[(size_t)prev * NID + stid];
                    travel = length / SPEED;
                    for (j = 0; j < len; j++) service += SVC[d->nodes[b + j]];
                    for (j = 0; j < len; j++) e2 += ENGE[d->nodes[b + j]];
                    energy = travel * FE + e2;
                    if (energy > cap + 1e-7) return 0;
                    drone_time += travel + service;
                }
            }
            if (drone_time > lim + 1e-7) return 0;
            continue;
        }
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            double drone_time = 0.0, cap = CAP[kind][di], lim = LIM[kind];
            for (t = 0; t < d->ntrips; t++) {
                int b = d->start[t], e = d->start[t + 1], len = e - b, prev = stid;
                double length = 0.0, service = 0.0, energy, travel, e2 = 0.0;
                if (len <= 0) continue;
                for (j = 0; j < len; j++) {
                    int nid = d->nodes[b + j];
                    int ti = (nid >= 0 && nid < NID) ? TIDX[nid] : -1;
                    if (ti < 0) return 0;
                    counts[ti]++;
                    if (!COVERG[(size_t)kind * NST * NT + (size_t)s * NT + ti]) return 0;
                    length += DIST[(size_t)prev * NID + nid];
                    prev = nid;
                }
                length += DIST[(size_t)prev * NID + stid];
                travel = length / SPEED;
                for (j = 0; j < len; j++) service += SVC[d->nodes[b + j]];
                for (j = 0; j < len; j++) e2 += ENGE[d->nodes[b + j]];
                energy = travel * FE + e2;
                if (energy > cap + 1e-7) return 0;
                drone_time += travel + service;
            }
            if (drone_time > lim + 1e-7) return 0;
        }
    }
    for (k = 0; k < NT; k++) if (counts[k] != 1) return 0;
    return 1;
}

/* ---------- JavaRandom ---------- */
typedef struct { uint64_t seed; int draws; } JR;

static inline uint32_t jr_bits(JR *r, int n) {
    r->seed = (r->seed * 0x5DEECE66DULL + 0xBULL) & MASK48;
    return (uint32_t)(r->seed >> (48 - n));
}

static uint32_t jr_randrange(JR *r, uint32_t bound) {
    uint32_t bits, value;
    r->draws++;
    if ((bound & (0u - bound)) == bound) return (uint32_t)(((uint64_t)bound * jr_bits(r, 31)) >> 31);
    for (;;) {
        bits = jr_bits(r, 31);
        value = bits % bound;
        if ((uint64_t)bits - value + (bound - 1) < (1ULL << 31)) return value;
    }
}

static double jr_random(JR *r) {
    uint32_t a, b;
    r->draws++;
    a = jr_bits(r, 26);
    b = jr_bits(r, 27);
    return (double)(((uint64_t)a << 27) + b) / 9007199254740992.0;
}

/* ---------- destroy ---------- */
static int build_entries(Sol *o) {
    int s, di, t, p, n = 0;
    for (s = 0; s < NST; s++) {
        if (!o->st[s].kind) continue;
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            if (d->total <= 1) continue;
            for (t = 0; t < d->ntrips; t++) {
                int b = d->start[t], e = d->start[t + 1];
                for (p = b; p < e; p++) {
                    if (n >= MAXN) { FAULT = 4; return n; }
                    e_si[n] = s; e_di[n] = di; e_ti[n] = t; e_pi[n] = p - b; e_nid[n] = d->nodes[p];
                    n++;
                }
            }
        }
    }
    return n;
}

static void sort_desc(double *val, int *idx, int n) {
    int i, j;
    for (i = 1; i < n; i++) {
        double v = val[i]; int k = idx[i];
        j = i - 1;
        while (j >= 0 && val[j] < v) { val[j + 1] = val[j]; idx[j + 1] = idx[j]; j--; }
        val[j + 1] = v; idx[j + 1] = k;
    }
}

static void sort_asc3(double *val, int *a, int *b, int n) {
    int i, j;
    for (i = 1; i < n; i++) {
        double v = val[i]; int x = a[i], y = b[i];
        j = i - 1;
        while (j >= 0 && val[j] > v) { val[j + 1] = val[j]; a[j + 1] = a[j]; b[j + 1] = b[j]; j--; }
        val[j + 1] = v; a[j + 1] = x; b[j + 1] = y;
    }
}

int r6_destroy(int src, int dst, int op, uint64_t seed, uint64_t *seed_out, int *draws_out,
               int *removed_out, int *nremoved_out) {
    Sol *o;
    JR rng;
    int s, di, t, i, n, nent, chosen = -1;
    rng.seed = seed; rng.draws = 0;
    r6_clone(src, dst);
    o = &S[dst];
    nent = build_entries(o);
    if (op == 2) {
        if (nent == 0) goto finish;
        i = (int)jr_randrange(&rng, (uint32_t)nent);
        d_remove(&o->st[e_si[i]].d[e_di[i]], e_ti[i], e_pi[i]);
        goto finish;
    }
    if (op == 0) {
        double gain = -INFINITY;
        for (i = 0; i < nent; i++) {
            Station *st = &o->st[e_si[i]];
            Drone *d = &st->d[e_di[i]];
            int b = d->start[e_ti[i]], len = d->start[e_ti[i] + 1] - b;
            double old_t = path_time(e_si[i], d->nodes + b, len), saving;
            d_remove(d, e_ti[i], e_pi[i]);
            saving = (old_t - path_time(e_si[i], d->nodes + b, len - 1)) * TCOST;
            if (saving > gain) {
                if (path_energy_seg(e_si[i], d->nodes + b, len - 1) < CAP[st->kind][e_di[i]]) {
                    gain = saving; chosen = i;
                }
            }
            d_insert(d, e_ti[i], e_pi[i], e_nid[i]);
        }
        if (chosen >= 0) {
            Drone *d = &o->st[e_si[chosen]].d[e_di[chosen]];
            if (d->start[e_ti[chosen] + 1] - d->start[e_ti[chosen]] > 1)
                d_remove(d, e_ti[chosen], e_pi[chosen]);
        }
        goto finish;
    }
    if (op == 1) {
        for (s = 0; s < NST; s++) {
            int depot = STID[s];
            for (di = 0; di < MAXDR; di++) {
                Drone *d = &o->st[s].d[di];
                int remaining = d->total;
                for (t = 0; t < d->ntrips; t++) {
                    int b = d->start[t], len = d->start[t + 1] - b, m = 0, p;
                    for (p = 0; p < len; p++) {
                        int nid = d->nodes[b + p], a, bb;
                        double saving;
                        if (remaining == 1) continue;
                        a = (p == 0) ? depot : d->nodes[b + p - 1];
                        bb = (p + 1 == len) ? depot : d->nodes[b + p + 1];
                        saving = DIST[(size_t)a * NID + nid] + DIST[(size_t)nid * NID + bb] - DIST[(size_t)a * NID + bb];
                        if (saving > 0) { scratch_val[m] = saving; scratch_idx[m] = p; m++; }
                    }
                    sort_desc(scratch_val, scratch_idx, m);
                    for (i = 0; i < m; i++) {
                        if (jr_random(&rng) <= 0.7 && remaining > 1) {
                            d_remove(d, t, scratch_idx[i]);
                            remaining--;
                            break;
                        }
                    }
                }
            }
        }
        goto finish;
    }
    /* op == 3 */
    {
        int ncand = 0;
        for (i = 0; i < NID; i++) cover_cache[i] = -1;
        for (i = 0; i < nent; i++) {
            int nid = e_nid[i];
            Drone *d = &o->st[e_si[i]].d[e_di[i]];
            int b = d->start[e_ti[i]], len = d->start[e_ti[i] + 1] - b;
            double score = 0.0;
            int j, ca;
            if (len < 2) continue;
            ca = cover_cache[nid];
            if (ca < 0) {
                int jj, tt = TIDX[nid];
                ca = 0;
                for (jj = 0; jj < NST; jj++) {
                    int kk = o->st[jj].kind;
                    if (kk && COVER[(size_t)kk * NST * NT + (size_t)jj * NT + tt]) { ca = 1; break; }
                }
                cover_cache[nid] = (signed char)ca;
            }
            for (j = 0; j < len; j++) {
                int other = d->nodes[b + j], cb;
                double w, dd;
                if (other == nid) continue;
                cb = cover_cache[other];
                if (cb < 0) {
                    int jj, tt = TIDX[other];
                    cb = 0;
                    for (jj = 0; jj < NST; jj++) {
                        int kk = o->st[jj].kind;
                        if (kk && COVER[(size_t)kk * NST * NT + (size_t)jj * NT + tt]) { cb = 1; break; }
                    }
                    cover_cache[other] = (signed char)cb;
                }
                w = (ca && cb) ? 0.8 : (ca || cb) ? 0.5 : 0.2;
                dd = DIST[(size_t)nid * NID + other];
                if (dd < 1e-6) dd = 1e-6;
                score += w / dd;
            }
            if (score > 0) { cand_idx[ncand] = i; cand_score[ncand] = score; ncand++; }
        }
        if (ncand == 0) goto finish;
        {
            double low = cand_score[0], high = cand_score[0], total = 0.0, draw, cum = 0.0;
            int pick = ncand - 1;
            for (i = 1; i < ncand; i++) {
                if (cand_score[i] < low) low = cand_score[i];
                if (cand_score[i] > high) high = cand_score[i];
            }
            for (i = 0; i < ncand; i++)
                cand_weight[i] = (d_abs(high - low) < 1e-9 ? 1.0 : (cand_score[i] - low) / (high - low)) + 1e-6;
            for (i = 0; i < ncand; i++) total += cand_weight[i];
            draw = jr_random(&rng) * total;
            for (i = 0; i < ncand; i++) {
                cum += cand_weight[i];
                if (draw <= cum) { pick = i; break; }
            }
            chosen = cand_idx[pick];
            d_remove(&o->st[e_si[chosen]].d[e_di[chosen]], e_ti[chosen], e_pi[chosen]);
        }
    }
finish:
    /* fidelity_ops_v5 returns the *input* solution when a post-removal state
     * fails raw_valid for op 0 and op 2 (op 1 and op 3 skip the gate). */
    if (op == 0 || op == 2) {
        if (!r6_valid(dst, 1)) r6_clone(src, dst);
    }
    memset(remmark, 0, (size_t)(NID + 1));
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &S[src].st[s].d[di];
            for (i = 0; i < d->total; i++) remmark[d->nodes[i]] = 1;
        }
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            for (i = 0; i < d->total; i++) remmark[d->nodes[i]] = 0;
        }
    n = 0;
    for (i = 0; i < NT; i++)
        if (remmark[TIDS[i]]) { removed_out[n++] = TIDS[i]; remmark[TIDS[i]] = 0; }
    *nremoved_out = n;
    *seed_out = rng.seed;
    *draws_out = rng.draws;
    return 1;
}

/* ---------- repair ---------- */
static void apply_option(Sol *o, int nid, int si, int di, int ti, int pos) {
    Drone *d = &o->st[si].d[di];
    if (ti >= d->ntrips) d_newtrip(d, nid);
    else d_insert(d, ti, pos, nid);
}

static int covered_pairs(Sol *o, int nid, int require_routes, int allow_empty_station,
                         int *out_si, int *out_di) {
    int s, di, n = 0, ti = TIDX[nid];
    for (s = 0; s < NST; s++) {
        int kind = o->st[s].kind, any = 0;
        if (!kind) continue;
        if (!COVER[(size_t)kind * NST * NT + (size_t)s * NT + ti]) continue;
        for (di = 0; di < MAXDR; di++) if (o->st[s].d[di].ntrips) { any = 1; break; }
        if (!any && !allow_empty_station) continue;
        for (di = 0; di < MAXDR; di++) {
            if (require_routes && !o->st[s].d[di].ntrips) continue;
            out_si[n] = s; out_di[n] = di; n++;
        }
    }
    return n;
}

int r6_repair(int slot, int op, const int *removed, int nremoved) {
    Sol *o;
    int idx;
    if (slot < 0 || slot >= MAXSLOT) return -1;
    if (op < 0 || op > 3 || nremoved < 0 || (nremoved > 0 && removed == NULL)) return -1;
    for (idx = 0; idx < nremoved; idx++) {
        int nid = removed[idx];
        if (nid < 0 || nid >= NID || TIDX[nid] < 0) return -1;
    }
    o = &S[slot];

    for (idx = 0; idx < nremoved; idx++) {
        int nid = removed[idx];
        int ps[MAXST * MAXDR], pd[MAXST * MAXDR], np, i;
        int best_si = -1, best_di = -1, best_ti = -1, best_pos = -1;
        int newpath_si = -1, newpath_di = -1, newpath_ti = -1;
        double bestscore = -INFINITY, min_delta = INFINITY;
        if (op == 3) {
            np = covered_pairs(o, nid, 0, 1, ps, pd);
            for (i = 0; i < np; i++) {
                Drone *d = &o->st[ps[i]].d[pd[i]];
                int kind = o->st[ps[i]].kind;
                if (d->ntrips) continue;
                if (path_energy_seg(ps[i], &nid, 1) <= CAP[kind][pd[i]] &&
                    path_time(ps[i], &nid, 1) <= LIM[kind]) {
                    newpath_si = ps[i]; newpath_di = pd[i]; newpath_ti = 0; break;
                }
            }
            if (newpath_si >= 0) { apply_option(o, nid, newpath_si, newpath_di, 0, 0); continue; }
        }
        if (op != 2) {
            np = covered_pairs(o, nid, (op == 0 || op == 1), op == 3, ps, pd);
            for (i = 0; i < np; i++) {
                int si = ps[i], dj = pd[i], t, m = 0, chosen = 0, total_done = 0;
                Drone *d = &o->st[si].d[dj];
                int kind = o->st[si].kind, depot = STID[si];
                double cap = CAP[kind][dj], lim = LIM[kind], total = 0.0;
                for (t = 0; t < d->ntrips; t++) {
                    int b = d->start[t], len = d->start[t + 1] - b, p;
                    for (p = 0; p <= len; p++) {
                        int a, bb;
                        if (m >= RANKCAP) { FAULT = 3; break; }
                        a = (p == 0) ? depot : d->nodes[b + p - 1];
                        bb = (p == len) ? depot : d->nodes[b + p];
                        rank_delta[m] = DIST[(size_t)a * NID + nid] + DIST[(size_t)nid * NID + bb] - DIST[(size_t)a * NID + bb];
                        rank_ti[m] = t; rank_pos[m] = p; m++;
                    }
                }
                sort_asc3(rank_delta, rank_ti, rank_pos, m);
                for (t = 0; t < m; t++) {
                    double delta = rank_delta[t], newtime, after, old_time;
                    int tt = rank_ti[t], pp = rank_pos[t], ok;
                    if (delta >= min_delta) break;
                    d_insert(d, tt, pp, nid);
                    ok = path_energy_seg(si, d->nodes + d->start[tt], d->start[tt + 1] - d->start[tt]) <= cap;
                    newtime = ok ? path_time(si, d->nodes + d->start[tt], d->start[tt + 1] - d->start[tt]) : 0.0;
                    d_remove(d, tt, pp);
                    if (!ok) continue;
                    if (!total_done) {
                        int z;
                        total = 0.0;
                        for (z = 0; z < d->ntrips; z++)
                            total += path_time(si, d->nodes + d->start[z], d->start[z + 1] - d->start[z]);
                        total_done = 1;
                    }
                    old_time = path_time(si, d->nodes + d->start[tt], d->start[tt + 1] - d->start[tt]);
                    after = total - old_time + newtime;
                    if (after > lim) continue;
                    min_delta = delta;
                    best_si = si; best_di = dj; best_ti = tt; best_pos = pp;
                    chosen = 1;
                    break;
                }
                if (!chosen && op == 0) {
                    double base = DIST[(size_t)depot * NID + nid];
                    if (base < min_delta) { min_delta = base; newpath_si = si; newpath_di = dj; newpath_ti = d->ntrips; }
                }
            }
            if (best_si >= 0) { apply_option(o, nid, best_si, best_di, best_ti, best_pos); continue; }
            if (newpath_si >= 0) { apply_option(o, nid, newpath_si, newpath_di, newpath_ti, 0); continue; }
            if (op == 1) {
                double mincost = INFINITY;
                int found_si = -1, found_di = -1;
                np = covered_pairs(o, nid, 1, 0, ps, pd);
                for (i = 0; i < np; i++) {
                    int si = ps[i], dj = pd[i], kind = o->st[si].kind;
                    double single = path_time(si, &nid, 1), cost = single * TCOST;
                    if (path_energy_seg(si, &nid, 1) > CAP[kind][dj]) continue;
                    if (cost <= LIM[kind] && cost < mincost) { mincost = cost; found_si = si; found_di = dj; }
                }
                if (found_si >= 0) { apply_option(o, nid, found_si, found_di, o->st[found_si].d[found_di].ntrips, 0); continue; }
            } else {
                double mincost = INFINITY;
                int found_si = -1, found_di = -1;
                np = covered_pairs(o, nid, 0, op == 3, ps, pd);
                for (i = 0; i < np; i++) {
                    int si = ps[i], dj = pd[i], kind = o->st[si].kind, z;
                    double single = path_time(si, &nid, 1), cost = single * TCOST, total = 0.0;
                    if (path_energy_seg(si, &nid, 1) > CAP[kind][dj]) continue;
                    for (z = 0; z < o->st[si].d[dj].ntrips; z++)
                        total += path_time(si, o->st[si].d[dj].nodes + o->st[si].d[dj].start[z],
                                           o->st[si].d[dj].start[z + 1] - o->st[si].d[dj].start[z]);
                    if (total + single <= LIM[kind] && cost < mincost) { mincost = cost; found_si = si; found_di = dj; }
                }
                if (found_si >= 0) { apply_option(o, nid, found_si, found_di, o->st[found_si].d[found_di].ntrips, 0); continue; }
                return 0;
            }
            continue;
        }
        /* op == 2 */
        np = covered_pairs(o, nid, 0, 1, ps, pd);
        for (i = 0; i < np; i++) {
            int si = ps[i], dj = pd[i], t, p;
            Drone *d = &o->st[si].d[dj];
            int kind = o->st[si].kind;
            double cap = CAP[kind][dj], lim = LIM[kind], total = 0.0;
            for (t = 0; t < d->ntrips; t++)
                total += path_time(si, d->nodes + d->start[t], d->start[t + 1] - d->start[t]);
            for (t = 0; t < d->ntrips; t++) {
                int b = d->start[t], len = d->start[t + 1] - b;
                double old_time = path_time(si, d->nodes + b, len);
                for (p = 0; p <= len; p++) {
                    double newtime, after, dtime, score;
                    int ok;
                    d_insert(d, t, p, nid);
                    ok = path_energy_seg(si, d->nodes + d->start[t], d->start[t + 1] - d->start[t]) <= cap;
                    newtime = ok ? path_time(si, d->nodes + d->start[t], d->start[t + 1] - d->start[t]) : 0.0;
                    d_remove(d, t, p);
                    if (!ok) continue;
                    after = total - old_time + newtime;
                    if (after > lim) continue;
                    dtime = newtime - old_time;
                    score = 0.6 * (lim - after) / lim + 0.4 / (1.0 + d_abs(dtime * TCOST));
                    if (score > bestscore) { bestscore = score; best_si = si; best_di = dj; best_ti = t; best_pos = p; newpath_si = -1; }
                }
            }
            {
                double single_time = path_time(si, &nid, 1), after = total + single_time;
                if (path_energy_seg(si, &nid, 1) <= cap && after <= lim) {
                    double score = (lim - after) / lim;
                    if (score > bestscore) { bestscore = score; best_si = -1; newpath_si = si; newpath_di = dj; newpath_ti = d->ntrips; }
                }
            }
        }
        if (best_si >= 0) { apply_option(o, nid, best_si, best_di, best_ti, best_pos); continue; }
        if (newpath_si >= 0) { apply_option(o, nid, newpath_si, newpath_di, newpath_ti, 0); continue; }
        return 0;
    }
    return 1;
}
