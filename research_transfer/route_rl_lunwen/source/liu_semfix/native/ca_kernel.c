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
static int remcnt[MAXN];
static uint64_t REPAIR_MASK = 0;
static uint64_t REPAIR_DMASK = 0;
static int REPAIR_ALLOW_EMPTY = 0;
static int REPAIR_STRICT_KIND = 0;
static int rm_out[MAXN];
static int tmp_start[4200];
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

static int covered_pairs(Sol *o, int nid, int require_routes, int *out_si, int *out_di) {
    int s, di, n = 0, ti = TIDX[nid];
    for (s = 0; s < NST; s++) {
        int kind = o->st[s].kind, any = 0;
        if (!kind) continue;
        if (REPAIR_MASK && !((REPAIR_MASK >> s) & 1ULL)) continue;
        if (!COVER[(size_t)kind * NST * NT + (size_t)s * NT + ti]) continue;
        for (di = 0; di < MAXDR; di++) if (o->st[s].d[di].ntrips) { any = 1; break; }
        if (!any && !REPAIR_ALLOW_EMPTY) continue;
        for (di = 0; di < MAXDR; di++) {
            if (REPAIR_STRICT_KIND && kind == 1 && di == 0) continue;
            if (REPAIR_DMASK && !((REPAIR_DMASK >> di) & 1ULL)) continue;
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
            np = covered_pairs(o, nid, 0, ps, pd);
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
            np = covered_pairs(o, nid, (op == 0 || op == 1) && !REPAIR_ALLOW_EMPTY, ps, pd);
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
                np = covered_pairs(o, nid, !REPAIR_ALLOW_EMPTY, ps, pd);
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
                np = covered_pairs(o, nid, 0, ps, pd);
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
        np = covered_pairs(o, nid, 0, ps, pd);
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


/* ================= CA-RL extensions (2026-10-30) =================
 * Additional primitives for coupling-aware joint neighborhoods.
 * They do not alter the r6_* reproduction path: with masks 0 the
 * existing repair semantics are unchanged.
 */
int r6_repair_joint(int slot, int op, const int *removed, int nremoved,
                    unsigned long long station_mask, unsigned long long drone_mask,
                    int allow_empty, int strict_kind) {
    int rc;
    uint64_t old_s = REPAIR_MASK, old_d = REPAIR_DMASK;
    int old_a = REPAIR_ALLOW_EMPTY, old_k = REPAIR_STRICT_KIND;
    REPAIR_MASK = station_mask; REPAIR_DMASK = drone_mask;
    REPAIR_ALLOW_EMPTY = allow_empty; REPAIR_STRICT_KIND = strict_kind;
    rc = r6_repair(slot, op, removed, nremoved);
    REPAIR_MASK = old_s; REPAIR_DMASK = old_d;
    REPAIR_ALLOW_EMPTY = old_a; REPAIR_STRICT_KIND = old_k;
    return rc;
}

int r6_repair_scoped(int slot, int op, const int *removed, int nremoved,
                     unsigned long long station_mask, unsigned long long drone_mask) {
    return r6_repair_joint(slot, op, removed, nremoved, station_mask, drone_mask, 0, 0);
}

/* Remove an explicit set of targets from whatever routes currently hold them.
 * Returns the number removed, or -1 if the input is invalid / not present
 * exactly once.  Empty trips are dropped. */
int r6_remove_ids(int slot, const int *ids, int nids) {
    Sol *o;
    int i, s, di, t;
    if (slot < 0 || slot >= MAXSLOT || nids < 0 || (nids > 0 && ids == NULL)) return -1;
    for (i = 0; i < NT; i++) { remmark[i] = 0; remcnt[i] = 0; }
    for (i = 0; i < nids; i++) {
        int nid = ids[i], ti;
        if (nid < 0 || nid >= NID) return -1;
        ti = TIDX[nid];
        if (ti < 0 || remmark[ti]) return -1;
        remmark[ti] = 1;
    }
    o = &S[slot];
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            for (i = 0; i < d->total; i++) {
                int ti = TIDX[d->nodes[i]];
                if (ti >= 0) remcnt[ti]++;
            }
        }
    for (i = 0; i < nids; i++) {
        int ti = TIDX[ids[i]];
        if (remcnt[ti] != 1) return -1;
    }
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            int w = 0, nt = 0;
            if (d->ntrips + 1 > 4200) { FAULT = 5; return -1; }
            memcpy(tmp_start, d->start, sizeof(int) * (size_t)(d->ntrips + 1));
            for (t = 0; t < d->ntrips; t++) {
                int b = tmp_start[t], e = tmp_start[t + 1], q, start = w;
                for (q = b; q < e; q++) {
                    int nid = d->nodes[q], ti = TIDX[nid];
                    if (ti >= 0 && remmark[ti]) continue;
                    d->nodes[w++] = nid;
                }
                if (w > start) { d->start[nt + 1] = w; nt++; }
            }
            d->ntrips = nt; d->total = w; d->start[0] = 0;
        }
    for (i = 0; i < NT; i++) remmark[i] = 0;
    return nids;
}



/* Exact structural equality of two solution slots.
 * Returns 1 if identical, 0 if different, -1 for invalid slots.
 */
int r6_same(int a, int b) {
    int si, di;
    if (a < 0 || a >= MAXSLOT || b < 0 || b >= MAXSLOT) return -1;
    for (si = 0; si < NST; si++) {
        if (S[a].st[si].kind != S[b].st[si].kind) return 0;
        for (di = 0; di < MAXDR; di++) {
            Drone *x = &S[a].st[si].d[di];
            Drone *y = &S[b].st[si].d[di];
            if (x->ntrips != y->ntrips || x->total != y->total) return 0;
            if (memcmp(x->start, y->start, sizeof(int) * (size_t)(x->ntrips + 1)) != 0)
                return 0;
            if (memcmp(x->nodes, y->nodes, sizeof(int) * (size_t)x->total) != 0)
                return 0;
        }
    }
    return 1;
}

/* Swap two target IDs at their existing route positions.
 * mode=1: different drones at the same DABS station.
 * mode=2: different trips of the same drone at the same station.
 * Feasibility is checked by the caller after the swap.
 */
int r6_swap_targets(int slot, int nid_a, int nid_b, int mode) {
    Sol *o;
    int s, di, ti, pi;
    int sa=-1, da=-1, ta=-1, pa=-1, sb=-1, db=-1, tb=-1, pb=-1;
    int ca=0, cb=0;
    if (slot < 0 || slot >= MAXSLOT || nid_a < 0 || nid_a >= NID ||
        nid_b < 0 || nid_b >= NID || nid_a == nid_b ||
        TIDX[nid_a] < 0 || TIDX[nid_b] < 0 || (mode != 1 && mode != 2))
        return 0;
    o = &S[slot];
    for (s = 0; s < NST; s++) {
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            for (ti = 0; ti < d->ntrips; ti++) {
                int b = d->start[ti], e = d->start[ti + 1];
                for (pi = 0; pi < e - b; pi++) {
                    int nid = d->nodes[b + pi];
                    if (nid == nid_a) {
                        sa=s; da=di; ta=ti; pa=b+pi; ca++;
                    }
                    if (nid == nid_b) {
                        sb=s; db=di; tb=ti; pb=b+pi; cb++;
                    }
                }
            }
        }
    }
    if (ca != 1 || cb != 1 || sa < 0 || sb < 0 || sa != sb) return 0;
    if (mode == 1) {
        if (o->st[sa].kind != 2 || da == db) return 0;
    } else {
        if (da != db || ta == tb) return 0;
    }
    {
        Drone *a = &o->st[sa].d[da];
        Drone *b = &o->st[sb].d[db];
        int tmp = a->nodes[pa];
        a->nodes[pa] = b->nodes[pb];
        b->nodes[pb] = tmp;
    }
    return 1;
}

/* First-improvement 2-opt inside one trip.  Returns the number of reversals. */
int r6_two_opt(int slot, int si, int di, int ti) {
    Sol *o;
    Drone *d;
    int b, e, n, a, c, improved = 0, passes = 0;
    double dep;
    if (slot < 0 || slot >= MAXSLOT || si < 0 || si >= NST || di < 0 || di >= MAXDR) return -1;
    o = &S[slot];
    if (ti < 0 || ti >= o->st[si].d[di].ntrips) return -1;
    d = &o->st[si].d[di];
    b = d->start[ti]; e = d->start[ti + 1]; n = e - b;
    if (n < 3) return 0;
    dep = STID[si];
    do {
        improved = 0;
        for (a = 0; a < n - 1; a++) {
            int pa = (a == 0) ? -1 : d->nodes[b + a - 1];
            int na = d->nodes[b + a];
            for (c = a + 1; c < n; c++) {
                int nc = d->nodes[b + c];
                int pb = (c + 1 == n) ? -1 : d->nodes[b + c + 1];
                double before = (pa < 0 ? DIST[(size_t)(int)dep * NID + na] : DIST[(size_t)pa * NID + na])
                              + (pb < 0 ? DIST[(size_t)nc * NID + (int)dep] : DIST[(size_t)nc * NID + pb]);
                double after = (pa < 0 ? DIST[(size_t)(int)dep * NID + nc] : DIST[(size_t)pa * NID + nc])
                             + (pb < 0 ? DIST[(size_t)na * NID + (int)dep] : DIST[(size_t)na * NID + pb]);
                if (after < before - 1e-12) {
                    int x = a, y = c;
                    while (x < y) { int tmp = d->nodes[b + x]; d->nodes[b + x] = d->nodes[b + y]; d->nodes[b + y] = tmp; x++; y--; }
                    improved = 1; passes++;
                    break;
                }
            }
            if (improved) break;
        }
    } while (improved && passes < 1000);
    return passes;
}

/* First-improvement 2-opt on every trip of one station. */
int r6_two_opt_station(int slot, int si) {
    int di, t, total = 0;
    Sol *o;
    if (slot < 0 || slot >= MAXSLOT || si < 0 || si >= NST) return -1;
    o = &S[slot];
    for (di = 0; di < MAXDR; di++)
        for (t = 0; t < o->st[si].d[di].ntrips; t++)
            total += r6_two_opt(slot, si, di, t);
    return total;
}


/* Exact port of official Init.java GreedyRouting semantics.
 * - nearest feasible open station assignment, preserving input target order;
 * - DABS: stable station-distance sort, alternate LD then SD;
 * - each drone repeatedly selects the nearest target feasible with enough
 *   energy and time remaining to inspect it and return to its own station.
 * This deliberately does NOT call generic min-delta repair.
 */
int r6_rebuild_official_greedy(int slot) {
    Sol *o;
    static int assigned[MAXST][MAXN];
    static int nassigned[MAXST];
    static int drone_targets[MAXST][MAXDR][MAXN];
    static int ndrone[MAXST][MAXDR];
    int s, k, i, j, di;
    if (slot < 0 || slot >= MAXSLOT) return -1;
    o = &S[slot];
    for (s = 0; s < NST; s++) {
        nassigned[s] = 0;
        ndrone[s][0] = ndrone[s][1] = 0;
    }

    /* Init.allocateTargetsToStations: nearest opened station that covers it.
       Strict '<' preserves the first station in the official station array on ties. */
    for (k = 0; k < NT; k++) {
        int nid = TIDS[k], best = -1;
        double best_dist = INFINITY;
        for (s = 0; s < NST; s++) {
            int kind = o->st[s].kind;
            double d;
            if (kind == 0) continue;
            if (!COVER[(size_t)kind * NST * NT + (size_t)s * NT + k]) continue;
            d = DIST[(size_t)STID[s] * NID + nid];
            if (d < best_dist) { best_dist = d; best = s; }
        }
        if (best < 0 || nassigned[best] >= MAXN) return 0;
        assigned[best][nassigned[best]++] = nid;
    }

    /* Clear all old trips while retaining station types. */
    for (s = 0; s < NST; s++) {
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            d->ntrips = 0;
            d->total = 0;
            d->start[0] = 0;
        }
        if (o->st[s].kind == 0 || nassigned[s] == 0) continue;

        if (o->st[s].kind == 2) {
            /* Java List.sort is stable: insertion sort moves only on strict >. */
            for (i = 1; i < nassigned[s]; i++) {
                int v = assigned[s][i];
                double dv = DIST[(size_t)STID[s] * NID + v];
                j = i - 1;
                while (j >= 0 &&
                       DIST[(size_t)STID[s] * NID + assigned[s][j]] > dv) {
                    assigned[s][j + 1] = assigned[s][j];
                    j--;
                }
                assigned[s][j + 1] = v;
            }
            /* assignTargetsToDrones: first LD, then SD, alternating. */
            for (i = 0; i < nassigned[s]; i++) {
                di = i & 1;
                drone_targets[s][di][ndrone[s][di]++] = assigned[s][i];
            }
            /* Java's one-target edge case moves the sole LD target to SD. */
            if (ndrone[s][1] == 0 && ndrone[s][0] > 0) {
                int v = drone_targets[s][0][0];
                for (i = 1; i < ndrone[s][0]; i++)
                    drone_targets[s][0][i - 1] = drone_targets[s][0][i];
                ndrone[s][0]--;
                drone_targets[s][1][ndrone[s][1]++] = v;
            }
        } else {
            /* SABS has only the small drone (slot 1 in the frozen encoding). */
            for (i = 0; i < nassigned[s]; i++)
                drone_targets[s][1][ndrone[s][1]++] = assigned[s][i];
        }
    }

    /* Init.planDroneRoutes / findClosestTarget, independently per drone. */
    for (s = 0; s < NST; s++) {
        int kind = o->st[s].kind;
        if (kind == 0) continue;
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            int rem = ndrone[s][di];
            int *pending = drone_targets[s][di];
            double close_time = LIM[kind];
            if (rem == 0) continue;
            while (rem > 0) {
                int current = STID[s];
                double battery = CAP[kind][di];
                double elapsed = 0.0;
                int trip_len_now = 0;
                for (;;) {
                    int best_i = -1;
                    double best_dist = INFINITY;
                    for (i = 0; i < rem; i++) {
                        int nid = pending[i];
                        double move_t = DTAB[(size_t)current * NID + nid];
                        double move_e = DENG[(size_t)current * NID + nid];
                        double return_t = DTAB[(size_t)nid * NID + STID[s]];
                        double return_e = DENG[(size_t)nid * NID + STID[s]];
                        double dist = DIST[(size_t)current * NID + nid];
                        if (battery >= move_e + ENGE[nid] + return_e &&
                            elapsed + move_t + SVC[nid] + return_t <= close_time &&
                            dist < best_dist) {
                            best_i = i;
                            best_dist = dist;
                        }
                    }
                    if (best_i < 0) break;
                    {
                        int nid = pending[best_i];
                        double move_t = DTAB[(size_t)current * NID + nid];
                        double move_e = DENG[(size_t)current * NID + nid];
                        if (trip_len_now == 0) {
                            d_newtrip(d, nid);
                        } else {
                            d_insert(d, d->ntrips - 1,
                                     trip_len(d, d->ntrips - 1), nid);
                        }
                        if (FAULT) return 0;
                        trip_len_now++;
                        battery -= move_e + ENGE[nid];
                        elapsed += move_t + SVC[nid];
                        current = nid;
                        for (i = best_i + 1; i < rem; i++)
                            pending[i - 1] = pending[i];
                        rem--;
                    }
                }
                /* Avoid the infinite loop present in the Java code if a
                   covered target is nevertheless unserviceable by this drone. */
                if (trip_len_now == 0) return 0;
            }
        }
    }
    return 1;
}

/* Approximate fast rebuild: nearest-station assignment followed by generic
 * min-delta repair. This is NOT the official Init.java GreedyRouting port;
 * use r6_rebuild_official_greedy when exact official semantics are required. */
int r6_rebuild_nearest(int slot) {
    Sol *o;
    static int list[MAXST][MAXN];
    static int cnt[MAXST];
    int s, di, i, j, k, ti, nid;
    uint64_t old_s = REPAIR_MASK, old_d = REPAIR_DMASK;
    int old_a = REPAIR_ALLOW_EMPTY, old_k = REPAIR_STRICT_KIND;
    if (slot < 0 || slot >= MAXSLOT) return -1;
    o = &S[slot];
    for (s = 0; s < NST; s++) cnt[s] = 0;
    for (k = 0; k < NT; k++) {
        int best = -1;
        double bd = INFINITY;
        nid = TIDS[k];
        for (s = 0; s < NST; s++) {
            int kind = o->st[s].kind;
            double d;
            if (!kind) continue;
            if (!COVER[(size_t)kind * NST * NT + (size_t)s * NT + k]) continue;
            d = DIST[(size_t)STID[s] * NID + nid];
            if (d < bd) { bd = d; best = s; }
        }
        if (best < 0) return 0;
        if (cnt[best] >= MAXN) return 0;
        list[best][cnt[best]++] = nid;
    }
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            d->ntrips = 0; d->total = 0; d->start[0] = 0;
        }
    for (s = 0; s < NST; s++) {
        if (!cnt[s]) continue;
        /* insertion sort by distance to the station, nearest first */
        for (i = 1; i < cnt[s]; i++) {
            int v = list[s][i];
            double dv = DIST[(size_t)STID[s] * NID + v];
            j = i - 1;
            while (j >= 0 && DIST[(size_t)STID[s] * NID + list[s][j]] > dv) {
                list[s][j + 1] = list[s][j];
                j--;
            }
            list[s][j + 1] = v;
        }
        REPAIR_MASK = 1ULL << s; REPAIR_DMASK = 0;
        REPAIR_ALLOW_EMPTY = 1; REPAIR_STRICT_KIND = 1;
        if (r6_repair(slot, 0, list[s], cnt[s]) != 1) {
            REPAIR_MASK = old_s; REPAIR_DMASK = old_d;
            REPAIR_ALLOW_EMPTY = old_a; REPAIR_STRICT_KIND = old_k;
            return 0;
        }
    }
    REPAIR_MASK = old_s; REPAIR_DMASK = old_d;
    REPAIR_ALLOW_EMPTY = old_a; REPAIR_STRICT_KIND = old_k;
    return 1;
}

/* Rebuild all routes from scratch for the current station types.
 * Targets are inserted in the given order by the same min-delta insertion
 * used by repair op 0, with empty stations/drones allowed. */
int r6_rebuild(int slot, const int *order, int norder) {
    Sol *o;
    int s, di, i, rc;
    uint64_t old_s = REPAIR_MASK, old_d = REPAIR_DMASK;
    int old_a = REPAIR_ALLOW_EMPTY, old_k = REPAIR_STRICT_KIND;
    if (slot < 0 || slot >= MAXSLOT || norder < 0 || (norder > 0 && order == NULL)) return -1;
    o = &S[slot];
    for (s = 0; s < NST; s++)
        for (di = 0; di < MAXDR; di++) {
            Drone *d = &o->st[s].d[di];
            d->ntrips = 0; d->total = 0; d->start[0] = 0;
        }
    REPAIR_MASK = 0; REPAIR_DMASK = 0;
    REPAIR_ALLOW_EMPTY = 1; REPAIR_STRICT_KIND = 1;
    rc = r6_repair(slot, 0, order, norder);
    REPAIR_MASK = old_s; REPAIR_DMASK = old_d;
    REPAIR_ALLOW_EMPTY = old_a; REPAIR_STRICT_KIND = old_k;
    return rc;
}

/* Evaluate the route-set cost and physical statistics of one station.
 * out: [0]=time, [1]=fixed, [2]=drone0 time, [3]=drone1 time,
 *      [4]=minimum trip energy slack, [5]=target count, [6]=trip count,
 *      [7]=drone0 minimum energy slack (0 when inactive), [8]=drone1 minimum
 *      energy slack (0 when inactive). A drone with no trips has full capacity. */
int r6_station_stats(int slot, int si, double *out) {
    Sol *o;
    int di, t, count = 0, nt = 0;
    double fixed = 0.0, total = 0.0, dtime[2] = {0.0, 0.0}, slack = INFINITY;
    double dslack[2] = {0.0, 0.0};
    if (slot < 0 || slot >= MAXSLOT || si < 0 || si >= NST || out == NULL) return 0;
    o = &S[slot];
    if (o->st[si].kind == 2) {
        fixed = 30.4 + 8.0 + 5.0;
        dslack[0] = CAP[2][0]; dslack[1] = CAP[2][1];
    } else if (o->st[si].kind == 1) {
        fixed = 22.8 + 5.0;
        dslack[1] = CAP[1][1];
    }
    for (di = 0; di < MAXDR; di++) {
        Drone *d = &o->st[si].d[di];
        for (t = 0; t < d->ntrips; t++) {
            int b = d->start[t], e = d->start[t + 1];
            double tm = path_time(si, d->nodes + b, e - b);
            double en = path_energy_raw(si, d->nodes + b, e - b);
            dtime[di] += tm; total += tm; nt++; count += (e - b);
            if (o->st[si].kind) {
                double cap = CAP[o->st[si].kind][di];
                if (cap - en < slack) slack = cap - en;
                if (cap - en < dslack[di]) dslack[di] = cap - en;
            }
        }
    }
    out[0] = total; out[1] = fixed; out[2] = dtime[0]; out[3] = dtime[1];
    out[4] = (slack == INFINITY ? 0.0 : slack); out[5] = (double)count; out[6] = (double)nt;
    out[7] = dslack[0]; out[8] = dslack[1];
    return 1;
}
