"""Run the ACE recovery micro-model (14.36M byte-level GPT) with pure numpy.
torch is unavailable in this environment, so the forward pass is reimplemented
from train_recovery_micro.py's architecture: 8 blocks, 8 heads, d_model 384,
tied embedding/head, exact GELU, LayerNorm eps 1e-5 (torch default).
"""
import json
import numpy as np
from math import erf
from pathlib import Path
from safetensors.numpy import load_file

ROOT = Path('/home/hatch/workspace/runlab/ace_recovery/ACE_ASIN_HHC_CP8_RECOVERY_20260726')
MDIR = ROOT / 'model' / 'CP8-ACE-Recovery-Micro-v0.1'
cfg = json.loads((MDIR / 'config.json').read_text())
W = load_file(str(MDIR / 'model.safetensors'))
assert 'head.weight' not in W, 'expected tied head (no head.weight in checkpoint)'

H, D = cfg['n_heads'], cfg['d_model'] // cfg['n_heads']
SQRT2 = np.sqrt(2.0)


def gelu(x):
    return 0.5 * x * (1.0 + np.array([[erf(v / SQRT2) for v in row] for row in x.reshape(-1, x.shape[-1])]).reshape(x.shape))


def ln(x, w, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    va = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(va + eps) * w + b


def attn(x, p):
    B, T, C = x.shape
    q, k, v = np.split(x @ W[p + 'attn.qkv.weight'].T, 3, axis=-1)

    def split(a):
        return a.reshape(B, T, H, D).transpose(0, 2, 1, 3)

    q, k, v = split(q), split(k), split(v)
    s = (q @ k.transpose(0, 1, 3, 2)) / np.sqrt(D)
    s = np.where(np.triu(np.ones((T, T), bool), 1), -1e9, s)
    s = s - s.max(-1, keepdims=True)
    e = np.exp(s)
    a = e / e.sum(-1, keepdims=True)
    y = (a @ v).transpose(0, 2, 1, 3).reshape(B, T, C)
    return y @ W[p + 'attn.proj.weight'].T


def block(x, i):
    p = f'blocks.{i}.'
    x = x + attn(ln(x, W[p + 'ln1.weight'], W[p + 'ln1.bias']), p)
    h = ln(x, W[p + 'ln2.weight'], W[p + 'ln2.bias'])
    h = h @ W[p + 'mlp.0.weight'].T + W[p + 'mlp.0.bias']
    h = gelu(h)
    h = h @ W[p + 'mlp.2.weight'].T + W[p + 'mlp.2.bias']
    return x + h


def forward(ids):
    x = W['tok.weight'][ids] + W['pos.weight'][:len(ids)]
    x = x[None, :, :]
    for i in range(cfg['n_layers']):
        x = block(x, i)
    x = ln(x, W['ln.weight'], W['ln.bias'])
    return x @ W['tok.weight'].T  # tied head


if __name__ == '__main__':
    # 1. Verification forward pass (same probe as verify_recovery_micro.py)
    probe = np.array([60, 124, 105, 110, 115, 116, 114, 117, 99, 116, 105, 111, 110, 124, 62])
    logits = forward(probe)
    assert logits.shape == (1, len(probe), cfg['vocab_size']), logits.shape
    assert np.isfinite(logits).all()
    print(json.dumps({'verified': True, 'checkpoint_load': 'PASS (numpy)',
                      'forward_pass': 'PASS (numpy)', 'logits_shape': list(logits.shape),
                      'finite_logits': True}, indent=2))

    # 2. Generation demo
    rng = np.random.default_rng(428)
    ids = list(b'CP8|ACE|')
    for _ in range(160):
        ctx = np.array(ids[-cfg['context_length']:])
        l = forward(ctx)[0, -1] / 0.8
        l = l - l.max()
        p = np.exp(l)
        p = p / p.sum()
        ids.append(int(rng.choice(cfg['vocab_size'], p=p)))
    print('--- sample ---')
    print(bytes(ids).decode('utf-8', errors='replace'))
