#!/usr/bin/env python3
"""
Wallet Hunt Scanner — Lightweight Version
Scans workspace for potential wallet addresses and keys.
Reports findings without exposing sensitive data.

CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
"""

import re
import json
import os
from pathlib import Path
from datetime import datetime, timezone

# Patterns
PATTERNS = {
    'eth_address': re.compile(r'0x[a-fA-F0-9]{40}'),
    'eth_pk': re.compile(r'[a-fA-F0-9]{64}'),
    'btc_address': re.compile(r'(?:1[a-km-zA-HJ-NP-Z1-9]{25,34}|3[a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})'),
    'sol_address': re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}'),
}

BIP39_WORDS = set([
    'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract', 'absurd', 'abuse',
    'access', 'accident', 'account', 'accuse', 'achieve', 'acid', 'acoustic', 'acquire', 'across', 'act',
    'action', 'actor', 'actress', 'actual', 'adapt', 'add', 'addict', 'address', 'adjust', 'admit',
    'adult', 'advance', 'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again', 'age', 'agent',
    'agree', 'ahead', 'aim', 'air', 'airport', 'aisle', 'alarm', 'album', 'alcohol', 'alert',
    'alien', 'all', 'alley', 'allow', 'almost', 'alone', 'alpha', 'already', 'also', 'alter',
    'always', 'amateur', 'amazing', 'among', 'amount', 'amused', 'analyst', 'anchor', 'ancient', 'anger',
    'angle', 'angry', 'animal', 'ankle', 'announce', 'annual', 'another', 'answer', 'antenna', 'antique',
    'anxiety', 'any', 'apart', 'apple', 'approve', 'april', 'arch', 'arctic', 'area', 'arena',
    'argue', 'armed', 'armor', 'army', 'around', 'arrange', 'arrest', 'arrive', 'arrow', 'art',
    'artefact', 'artist', 'artwork', 'ask', 'aspect', 'assault', 'asset', 'assist', 'assume', 'asthma',
    'athlete', 'atom', 'attack', 'attend', 'attitude', 'attract', 'auction', 'audit', 'august', 'aunt',
    'author', 'auto', 'autumn', 'average', 'avocado', 'avoid', 'awake', 'aware', 'away', 'awesome',
    'awful', 'awkward', 'axis', 'baby', 'bachelor', 'bacon', 'badge', 'bag', 'balance', 'balcony',
    'ball', 'bamboo', 'banana', 'banner', 'bar', 'barely', 'bargain', 'barrel', 'base', 'basic',
    'basket', 'battle', 'beach', 'bean', 'beauty', 'because', 'become', 'beef', 'before', 'begin',
    'behave', 'behind', 'believe', 'below', 'belt', 'bench', 'benefit', 'best', 'betray', 'better',
    'between', 'beyond', 'bicycle', 'bid', 'bike', 'bind', 'biology', 'bird', 'birth', 'bitter',
    'black', 'blade', 'blame', 'blanket', 'blast', 'bleak', 'bless', 'blind', 'blood', 'blossom',
    'blouse', 'blue', 'blur', 'blush', 'board', 'boat', 'body', 'boil', 'bomb', 'bone',
    'bonus', 'book', 'boost', 'border', 'boring', 'borrow', 'boss', 'bottom', 'bounce', 'box',
    'boy', 'bracket', 'brain', 'brand', 'brass', 'brave', 'bread', 'breeze', 'brick', 'bridge',
    'brief', 'bright', 'bring', 'brisk', 'broccoli', 'broken', 'bronze', 'broom', 'brother', 'brown',
    'brush', 'bubble', 'buddy', 'budget', 'buffalo', 'build', 'bulb', 'bulk', 'bullet', 'bundle',
    'bunker', 'burden', 'burger', 'burst', 'bus', 'business', 'busy', 'butter', 'buyer', 'buzz',
    'cabbage', 'cabin', 'cable', 'cactus', 'cage', 'cake', 'call', 'calm', 'camera', 'camp',
    'can', 'canal', 'cancel', 'candy', 'cannon', 'canoe', 'canvas', 'canyon', 'capable', 'capital',
    'captain', 'car', 'carbon', 'card', 'cargo', 'carpet', 'carry', 'cart', 'case', 'cash',
    'casino', 'castle', 'casual', 'cat', 'catalog', 'catch', 'category', 'cattle', 'caught', 'cause',
    'caution', 'cave', 'ceiling', 'celery', 'cement', 'census', 'century', 'cereal', 'certain', 'chair',
    'chalk', 'champion', 'change', 'chaos', 'chapter', 'charge', 'chase', 'chat', 'cheap', 'check',
    'cheese', 'chef', 'cherry', 'chest', 'chicken', 'chief', 'child', 'chimney', 'choice', 'choose',
    'chronic', 'chuckle', 'chunk', 'churn', 'cigar', 'cinnamon', 'circle', 'citizen', 'city', 'civil',
    'claim', 'clap', 'clarify', 'claw', 'clay', 'clean', 'clerk', 'click', 'client', 'cliff',
    'climb', 'clinic', 'clip', 'clock', 'clog', 'close', 'cloth', 'cloud', 'clown', 'club',
    'clump', 'cluster', 'clutch', 'coach', 'coast', 'coconut', 'code', 'coffee', 'coil', 'coin',
    'collect', 'color', 'column', 'combine', 'come', 'comfort', 'comic', 'common', 'company', 'concert',
    'conduct', 'confirm', 'connect', 'consent', 'consider', 'control', 'convert', 'convince', 'cook', 'cool',
    'copper', 'copy', 'coral', 'core', 'corn', 'correct', 'cost', 'cotton', 'couch', 'country',
    'couple', 'course', 'cousin', 'cover', 'coyote', 'crack', 'cradle', 'craft', 'cram', 'crane',
    'crash', 'crater', 'crawl', 'crazy', 'cream', 'credit', 'creek', 'crew', 'cricket', 'crime',
    'crisp', 'critic', 'crop', 'cross', 'crouch', 'crowd', 'crucial', 'cruel', 'cruise', 'crumble',
    'crunch', 'crush', 'cry', 'crystal', 'cube', 'culture', 'cupboard', 'curious', 'current', 'curtain',
    'curve', 'cushion', 'custom', 'cute', 'cycle', 'dad', 'damage', 'damp', 'dance', 'danger',
    'daring', 'dash', 'daughter', 'dawn', 'day', 'deal', 'debate', 'debris', 'decade', 'december',
    'decide', 'decline', 'decorate', 'decrease', 'deer', 'defense', 'define', 'defy', 'degree', 'delay',
    'deliver', 'demand', 'denial', 'dentist', 'deny', 'depart', 'depend', 'deposit', 'depth', 'deputy',
    'derive', 'describe', 'desert', 'design', 'desk', 'despair', 'destroy', 'detail', 'detect', 'develop',
    'device', 'devote', 'diagram', 'dial', 'diamond', 'diary', 'dice', 'diesel', 'diet', 'differ',
    'digital', 'dignity', 'dilemma', 'dinner', 'dinosaur', 'direct', 'dirt', 'disagree', 'discover', 'disease',
    'dish', 'dismiss', 'display', 'distance', 'divert', 'divide', 'divorce', 'dizzy', 'doctor', 'document',
    'dog', 'doll', 'dolphin', 'domain', 'donate', 'donkey', 'donor', 'door', 'dose', 'double',
    'dove', 'draft', 'dragon', 'drain', 'drama', 'drastic', 'draw', 'dream', 'dress', 'drift',
    'drill', 'drink', 'drive', 'drop', 'drum', 'dry', 'duck', 'dumb', 'dune', 'during',
    'dust', 'dutch', 'duty', 'dwarf', 'dynamic', 'eager', 'eagle', 'early', 'earn', 'earth',
    'ease', 'east', 'edge', 'edit', 'educate', 'effort', 'egg', 'eight', 'either', 'elbow',
    'elder', 'electric', 'elegant', 'element', 'elephant', 'elicit', 'elite', 'else', 'embark', 'embody',
    'embrace', 'emerge', 'emotion', 'employ', 'empty', 'enable', 'enact', 'end', 'endless', 'enemy',
    'energy', 'enforce', 'engage', 'engine', 'enjoy', 'enlist', 'enough', 'enrich', 'enroll', 'ensure',
    'enter', 'entire', 'entry', 'envelope', 'episode', 'equal', 'equip', 'era', 'erase', 'erode',
    'erosion', 'error', 'erupt', 'escape', 'essay', 'estate', 'eternal', 'ethics', 'evacuate', 'evade',
    'evaluate', 'event', 'ever', 'every', 'evidence', 'evil', 'evoke', 'evolve', 'exact', 'example',
    'excess', 'exchange', 'excite', 'exclude', 'excuse', 'execute', 'exercise', 'exhaust', 'exhibit', 'exile',
    'exist', 'exit', 'exotic', 'expand', 'expect', 'expire', 'explain', 'expose', 'express', 'extend',
    'extra', 'eye', 'eyebrow', 'fabric', 'face', 'facility', 'fact', 'factor', 'factory', 'fade',
    'faint', 'faith', 'fall', 'false', 'fame', 'family', 'famous', 'fan', 'fancy', 'fantasy',
    'farm', 'fashion', 'fat', 'fatal', 'father', 'fatigue', 'fault', 'favorite', 'feature', 'february',
    'federal', 'fee', 'feed', 'feel', 'female', 'fence', 'festival', 'fetch', 'fever', 'few',
    'fiber', 'fiction', 'field', 'fiend', 'fierce', 'fifth', 'fight', 'figure', 'file', 'fill',
    'film', 'filter', 'final', 'find', 'fine', 'finger', 'finish', 'fire', 'firm', 'first',
    'fish', 'fist', 'fit', 'fitness', 'fix', 'flag', 'flame', 'flash', 'flat', 'flavor',
    'flee', 'flesh', 'flight', 'flip', 'float', 'flock', 'floor', 'flour', 'flow', 'flower',
    'flu', 'fluid', 'flush', 'fly', 'foam', 'focus', 'fog', 'foil', 'fold', 'follow',
    'food', 'foot', 'force', 'forest', 'forget', 'fork', 'form', 'formal', 'formula', 'fortune',
    'forward', 'fossil', 'foster', 'found', 'fox', 'fragile', 'frame', 'frequent', 'fresh', 'friend',
    'fringe', 'frog', 'front', 'frost', 'frown', 'frozen', 'fruit', 'fuel', 'fun', 'funny',
    'furnace', 'fury', 'future', 'gadget', 'gain', 'galaxy', 'gallery', 'game', 'gap', 'garage',
    'garbage', 'garden', 'garlic', 'gas', 'gasp', 'gate', 'gather', 'gauge', 'gaze', 'gear',
    'gender', 'gene', 'general', 'genius', 'genre', 'gentle', 'genuine', 'gesture', 'ghost', 'giant',
    'gift', 'giggle', 'ginger', 'giraffe', 'girl', 'give', 'glad', 'glance', 'glare', 'glass',
    'glide', 'glimpse', 'globe', 'gloom', 'glory', 'glove', 'glow', 'glue', 'goat', 'gold',
    'good', 'goose', 'gossip', 'govern', 'gown', 'grab', 'grace', 'grade', 'gradual', 'grain',
    'grand', 'grant', 'grape', 'grass', 'gravity', 'gray', 'great', 'green', 'grid', 'grief',
    'grit', 'grocery', 'ground', 'group', 'grow', 'grunt', 'guard', 'guess', 'guest', 'guide',
    'guilt', 'guitar', 'gun', 'gym', 'habit', 'hair', 'half', 'hammer', 'hamster', 'hand',
    'happy', 'harbor', 'hard', 'harsh', 'harvest', 'hat', 'have', 'hawk', 'hazard', 'head',
    'health', 'heart', 'heavy', 'hedgehog', 'height', 'hello', 'help', 'hen', 'hero', 'hidden',
    'high', 'hill', 'hint', 'hip', 'hire', 'history', 'hobby', 'hockey', 'hold', 'hole',
    'holiday', 'hollow', 'holy', 'home', 'honey', 'hood', 'hope', 'horn', 'horror', 'horse',
    'host', 'hotel', 'hour', 'house', 'hover', 'huge', 'human', 'humble', 'humor', 'hundred',
    'hungry', 'hunt', 'hurdle', 'hurry', 'hurt', 'husband', 'hybrid', 'ice', 'icon', 'idea',
    'identify', 'idle', 'ignore', 'ill', 'illegal', 'illness', 'image', 'imitate', 'immense', 'immune',
    'impact', 'impose', 'improve', 'impulse', 'inch', 'include', 'income', 'increase', 'index', 'indicate',
    'indoor', 'industry', 'infant', 'inflict', 'inform', 'inhale', 'inject', 'injure', 'inmate', 'inner',
    'innocent', 'input', 'inquiry', 'insane', 'insect', 'insert', 'inside', 'insight', 'insist', 'inspire',
    'install', 'intact', 'interest', 'into', 'invest', 'invite', 'involve', 'iron', 'island', 'isolate',
    'issue', 'item', 'ivory', 'jacket', 'jaguar', 'jar', 'jazz', 'jealous', 'jeans', 'jelly',
    'jewel', 'job', 'jog', 'join', 'joke', 'journey', 'joy', 'judge', 'juice', 'jump',
    'jungle', 'junior', 'junk', 'jury', 'just', 'kangaroo', 'keen', 'keep', 'ketchup', 'key',
    'kick', 'kid', 'kidney', 'kind', 'kingdom', 'kiss', 'kit', 'kitchen', 'kite', 'kitten',
    'kiwi', 'knee', 'knife', 'knock', 'know', 'lab', 'label', 'labor', 'ladder', 'lady',
    'lake', 'lamp', 'language', 'large', 'laser', 'last', 'late', 'laugh', 'laundry', 'law',
    'lawn', 'lawsuit', 'layer', 'lazy', 'lead', 'leaf', 'league', 'lean', 'learn', 'leave',
    'lecture', 'left', 'leg', 'legal', 'legend', 'leisure', 'lemon', 'lend', 'length', 'lens',
    'leopard', 'lesson', 'letter', 'level', 'liar', 'liberty', 'library', 'license', 'life', 'lift',
    'light', 'like', 'limb', 'limit', 'link', 'lion', 'liquid', 'list', 'little', 'live',
    'lizard', 'load', 'loan', 'lobster', 'local', 'lock', 'locust', 'lodge', 'log', 'lonely',
    'long', 'loop', 'lottery', 'loud', 'love', 'loyal', 'luck', 'luggage', 'lumber', 'lunar',
    'lunch', 'luxury', 'lyrics', 'machine', 'mad', 'magic', 'magnet', 'maid', 'mail', 'main',
    'major', 'make', 'mammal', 'man', 'manage', 'mandate', 'mango', 'mansion', 'manual', 'maple',
    'marble', 'march', 'margin', 'marine', 'market', 'marriage', 'mask', 'mass', 'master', 'match',
    'material', 'math', 'matrix', 'matter', 'maximum', 'maze', 'meadow', 'mean', 'measure', 'meat',
    'mechanic', 'medal', 'media', 'melody', 'melt', 'member', 'memory', 'menu', 'mercy', 'merge',
    'merit', 'merry', 'mesh', 'message', 'metal', 'method', 'middle', 'midnight', 'milk', 'mill',
    'million', 'mimic', 'mind', 'minimum', 'minister', 'minor', 'mint', 'minute', 'miracle', 'mirror',
    'misery', 'miss', 'mistake', 'mix', 'mobile', 'model', 'modify', 'mom', 'moment', 'monitor',
    'monkey', 'month', 'moon', 'moral', 'more', 'morning', 'mosquito', 'mother', 'motion', 'motor',
    'mountain', 'mouse', 'move', 'movie', 'much', 'muffin', 'mule', 'multiply', 'muscle', 'museum',
    'mushroom', 'music', 'must', 'mutual', 'myself', 'mystery', 'myth', 'naive', 'name', 'napkin',
    'narrow', 'nasty', 'nation', 'nature', 'near', 'neck', 'need', 'negative', 'neglect', 'neither',
    'nerve', 'nest', 'net', 'network', 'neutral', 'never', 'news', 'next', 'nice', 'niche',
    'night', 'nine', 'noble', 'node', 'noise', 'nominee', 'noodle', 'normal', 'north', 'nose',
    'notable', 'note', 'nothing', 'notice', 'novel', 'now', 'nuclear', 'number', 'nurse', 'nut',
    'oak', 'obey', 'object', 'oblige', 'obscure', 'observe', 'obtain', 'obvious', 'occur', 'ocean',
    'october', 'odor', 'off', 'offer', 'office', 'often', 'oil', 'okay', 'old', 'olive',
    'olympic', 'omit', 'once', 'one', 'onion', 'online', 'only', 'open', 'opera', 'opinion',
    'opponent', 'opportunity', 'opposite', 'oppress', 'opt', 'optic', 'option', 'orange', 'orbit', 'orchard',
    'order', 'ordinary', 'organ', 'orient', 'original', 'orphan', 'ostrich', 'other', 'outdoor', 'outer',
    'outlet', 'outline', 'output', 'outside', 'oval', 'oven', 'over', 'own', 'owner', 'oxygen',
    'oyster', 'ozone', 'pact', 'paddle', 'page', 'paint', 'pair', 'palace', 'palm', 'pan',
    'panel', 'panic', 'panther', 'paper', 'parade', 'parent', 'park', 'parrot', 'party', 'pass',
    'patch', 'path', 'patient', 'patrol', 'pattern', 'pause', 'pave', 'payment', 'peace', 'peanut',
    'pear', 'peasant', 'pelican', 'pen', 'penalty', 'pencil', 'people', 'pepper', 'perfect', 'permit',
    'person', 'pet', 'phone', 'photo', 'phrase', 'physical', 'piano', 'picnic', 'picture', 'piece',
    'pig', 'pigeon', 'pill', 'pilot', 'pink', 'pioneer', 'pipe', 'pistol', 'pitch', 'pizza',
    'place', 'planet', 'plastic', 'plate', 'play', 'please', 'pledge', 'pluck', 'plug', 'plunge',
    'poem', 'poet', 'point', 'polar', 'pole', 'police', 'pond', 'pony', 'pool', 'popular',
    'port', 'pose', 'position', 'possible', 'post', 'potato', 'pottery', 'poverty', 'powder', 'power',
    'practice', 'praise', 'predict', 'prefer', 'prepare', 'present', 'pretty', 'prevent', 'price', 'pride',
    'primary', 'print', 'priority', 'prison', 'private', 'prize', 'problem', 'process', 'produce', 'profit',
    'program', 'project', 'promote', 'proof', 'property', 'prosper', 'protect', 'proud', 'provide', 'public',
    'pudding', 'pull', 'pulp', 'pulse', 'pumpkin', 'punch', 'pupil', 'puppy', 'purchase', 'purple',
    'purpose', 'push', 'put', 'puzzle', 'pyramid', 'quality', 'quantum', 'quarter', 'queen', 'question',
    'quick', 'quiet', 'quilt', 'quit', 'quiz', 'quote', 'rabbit', 'raccoon', 'race', 'rack',
    'radar', 'radio', 'rail', 'rain', 'raise', 'rally', 'ramp', 'ranch', 'random', 'range',
    'rapid', 'rare', 'rate', 'rather', 'raven', 'raw', 'razor', 'ready', 'real', 'reason',
    'rebel', 'recall', 'receive', 'recipe', 'record', 'recycle', 'reduce', 'reflect', 'reform', 'refuse',
    'region', 'regret', 'regular', 'reject', 'relax', 'release', 'relief', 'rely', 'remain', 'remember',
    'remind', 'remove', 'render', 'renew', 'rent', 'repair', 'repeat', 'replace', 'report', 'require',
    'rescue', 'resemble', 'resist', 'resource', 'response', 'rest', 'result', 'retire', 'retreat', 'return',
    'reunion', 'reveal', 'review', 'reward', 'rhythm', 'rib', 'ribbon', 'rice', 'rich', 'ride',
    'ridge', 'rifle', 'right', 'rigid', 'ring', 'riot', 'ripple', 'risk', 'ritual', 'rival',
    'river', 'road', 'roast', 'robot', 'robust', 'rocket', 'romance', 'roof', 'room', 'rope',
    'rose', 'rotate', 'rough', 'round', 'route', 'royal', 'rubber', 'rude', 'rug', 'rule',
    'run', 'rural', 'rush', 'russia', 'rust', 'sack', 'sacred', 'sad', 'saddle', 'sadness',
    'safe', 'sail', 'salad', 'salmon', 'salon', 'salt', 'salute', 'same', 'sample', 'sand',
    'satisfy', 'satoshi', 'sauce', 'sausage', 'save', 'say', 'scale', 'scan', 'scare', 'scatter',
    'scene', 'scheme', 'school', 'science', 'scissors', 'scorpion', 'scout', 'scrap', 'screen', 'script',
    'scroll', 'scrub', 'sea', 'search', 'season', 'seat', 'second', 'secret', 'section', 'security',
    'seed', 'seek', 'segment', 'select', 'sell', 'seminar', 'senior', 'sense', 'sentence', 'series',
    'service', 'session', 'settle', 'seven', 'shadow', 'shaft', 'shallow', 'shape', 'share', 'shark',
    'sharp', 'shave', 'sheep', 'sheet', 'shelf', 'shell', 'shield', 'shift', 'shine', 'ship',
    'shirt', 'shiver', 'shock', 'shoe', 'shoot', 'shop', 'short', 'shoulder', 'shove', 'show',
    'shrimp', 'shrug', 'shuffle', 'shy', 'sibling', 'sick', 'side', 'siege', 'sight', 'sign',
    'silent', 'silk', 'silly', 'silver', 'similar', 'simple', 'since', 'sing', 'siren', 'sister',
    'sit', 'six', 'size', 'skate', 'sketch', 'ski', 'skill', 'skin', 'skirt', 'skull',
    'sky', 'slab', 'slam', 'sleep', 'slice', 'slide', 'slight', 'slim', 'slogan', 'slot',
    'slow', 'slush', 'small', 'smart', 'smash', 'smell', 'smile', 'smoke', 'smooth', 'snack',
    'snake', 'snap', 'sneeze', 'snow', 'soap', 'soccer', 'social', 'sock', 'soda', 'soft',
    'solar', 'soldier', 'solid', 'solve', 'someone', 'song', 'soon', 'sorry', 'sort', 'soul',
    'sound', 'soup', 'source', 'south', 'space', 'spare', 'spatial', 'spawn', 'speak', 'special',
    'speed', 'spell', 'spend', 'sphere', 'spice', 'spider', 'spike', 'spin', 'spine', 'spirit',
    'split', 'spoil', 'sponge', 'spoon', 'sport', 'spot', 'spray', 'spread', 'spring', 'spy',
    'square', 'squeeze', 'squirrel', 'stable', 'stadium', 'staff', 'stage', 'stain', 'stair', 'stake',
    'stall', 'stamp', 'stand', 'star', 'stare', 'start', 'state', 'stay', 'steak', 'steal',
    'steam', 'steel', 'stem', 'step', 'stereo', 'stew', 'stick', 'stiff', 'still', 'sting',
    'stock', 'stomach', 'stone', 'stool', 'story', 'stove', 'strategy', 'street', 'strike', 'strong',
    'struggle', 'student', 'stuff', 'stumble', 'style', 'subject', 'submit', 'subway', 'success', 'such',
    'sudden', 'suffer', 'sugar', 'suggest', 'suit', 'summer', 'sun', 'super', 'supply', 'supreme',
    'sure', 'surface', 'surge', 'surprise', 'surround', 'survey', 'survival', 'suspect', 'sustain', 'swallow',
    'swamp', 'swap', 'swarm', 'swear', 'sweet', 'swift', 'swim', 'swing', 'switch', 'sword',
    'symbol', 'symptom', 'syrup', 'system', 'table', 'tackle', 'tag', 'tail', 'talent', 'talk',
    'tank', 'tape', 'target', 'task', 'taste', 'tattoo', 'taxi', 'teach', 'team', 'tear',
    'tease', 'tech', 'teen', 'teeth', 'tell', 'temper', 'temple', 'tempo', 'tend', 'tennis',
    'tent', 'term', 'test', 'text', 'thank', 'that', 'theme', 'then', 'theory', 'there',
    'they', 'thick', 'thing', 'think', 'third', 'thirst', 'this', 'thorn', 'those', 'thought',
    'thread', 'threat', 'three', 'thrive', 'throat', 'thumb', 'thunder', 'ticket', 'tide', 'tiger',
    'tight', 'tile', 'timber', 'time', 'tiny', 'tip', 'tired', 'tissue', 'title', 'toast',
    'tobacco', 'today', 'toe', 'together', 'toilet', 'token', 'tomato', 'tomorrow', 'tone', 'tongue',
    'tonight', 'tool', 'tooth', 'top', 'topic', 'torch', 'tornado', 'tortoise', 'toss', 'total',
    'touch', 'tough', 'tour', 'toward', 'tower', 'town', 'toy', 'track', 'trade', 'traffic',
    'tragic', 'train', 'transfer', 'trap', 'trash', 'travel', 'tray', 'treat', 'tree', 'trend',
    'trial', 'tribe', 'trick', 'trigger', 'trim', 'trip', 'trophy', 'trouble', 'truck', 'true',
    'trumpet', 'trust', 'truth', 'try', 'tube', 'tuition', 'tumble', 'tuna', 'tunnel', 'turkey',
    'turn', 'turtle', 'twelve', 'twenty', 'twice', 'twin', 'twist', 'type', 'typical', 'ugly',
    'umbrella', 'unable', 'unaware', 'uncle', 'uncover', 'under', 'undo', 'unfair', 'unfold', 'unhappy',
    'uniform', 'unique', 'unit', 'universe', 'unknown', 'unlock', 'until', 'unusual', 'unveil', 'update',
    'upgrade', 'uphold', 'upon', 'upper', 'upset', 'urban', 'urge', 'usage', 'use', 'used',
    'useful', 'useless', 'usual', 'utility', 'vacant', 'vacuum', 'vague', 'valid', 'valley', 'valve',
    'van', 'vanish', 'vapor', 'various', 'vast', 'vault', 'vehicle', 'velvet', 'vendor', 'venture',
    'verb', 'verify', 'version', 'very', 'vessel', 'veteran', 'viable', 'vibrant', 'vicious', 'victory',
    'video', 'view', 'village', 'vintage', 'violin', 'virtual', 'virus', 'visa', 'visit', 'visual',
    'vital', 'vivid', 'vocal', 'voice', 'volcano', 'volume', 'vote', 'voyage', 'wage', 'wagon',
    'waist', 'wait', 'walk', 'wall', 'walnut', 'want', 'war', 'warm', 'warrior', 'wash',
    'wasp', 'waste', 'water', 'wave', 'way', 'wealth', 'weapon', 'wear', 'weasel', 'weather',
    'web', 'wedding', 'weekend', 'weird', 'welcome', 'west', 'wet', 'whale', 'what', 'wheat',
    'wheel', 'when', 'where', 'whip', 'whisper', 'whistle', 'white', 'who', 'whole', 'why',
    'wicked', 'wide', 'width', 'wife', 'wild', 'will', 'win', 'wind', 'window', 'wine',
    'wing', 'wink', 'winner', 'winter', 'wire', 'wisdom', 'wise', 'wish', 'witness', 'wolf',
    'woman', 'wonder', 'wood', 'wool', 'word', 'work', 'world', 'worry', 'worth', 'wound',
    'wrap', 'wreck', 'wrestle', 'wrist', 'write', 'wrong', 'yard', 'year', 'yellow', 'you',
    'young', 'youth', 'zebra', 'zero', 'zone', 'zoo'
])


def scan_workspace(root_path='.', exclude=None):
    """Scan workspace for wallet-like patterns."""
    if exclude is None:
        exclude = {'.git', '__pycache__', 'node_modules', '.zip', '.tar'}
    
    findings = {
        'eth_addresses': [],
        'btc_addresses': [],
        'sol_addresses': [],
        'potential_pks': [],
        'seed_phrases': [],
        'scanned_files': 0
    }
    
    root = Path(root_path).resolve()
    
    for filepath in root.rglob('*'):
        if not filepath.is_file():
            continue
        
        # Skip excluded dirs
        if any(part.startswith('.') or part in exclude for part in filepath.parts):
            continue
        
        try:
            content = filepath.read_text(errors='ignore')
            findings['scanned_files'] += 1
        except (UnicodeDecodeError, PermissionError):
            continue
        
        rel_path = str(filepath.relative_to(root))
        
        # ETH addresses
        for match in PATTERNS['eth_address'].finditer(content):
            findings['eth_addresses'].append({
                'path': rel_path,
                'match': match.group(),
                'context': content[max(0, match.start()-20):match.end()+20].replace('\n', ' ')
            })
        
        # BTC addresses
        for match in PATTERNS['btc_address'].finditer(content):
            findings['btc_addresses'].append({
                'path': rel_path,
                'match': match.group(),
                'context': content[max(0, match.start()-20):match.end()+20].replace('\n', ' ')
            })
        
        # SOL addresses
        for match in PATTERNS['sol_address'].finditer(content):
            findings['sol_addresses'].append({
                'path': rel_path,
                'match': match.group(),
                'context': content[max(0, match.start()-20):match.end()+20].replace('\n', ' ')
            })
        
        # Potential private keys (64 hex)
        for match in PATTERNS['eth_pk'].finditer(content):
            # Skip if it's an ETH address without 0x
            if not content[match.start()-2:match.start()] == '0x':
                findings['potential_pks'].append({
                    'path': rel_path,
                    'match': match.group()[:8] + '...' + match.group()[-8:],
                    'warning': 'POTENTIAL PRIVATE KEY — VERIFY BEFORE HANDLING',
                    'context': content[max(0, match.start()-20):match.end()+20].replace('\n', ' ')
                })
        
        # Seed phrases (12+ BIP39 words in sequence)
        words = re.findall(r'\b[a-z]+\b', content.lower())
        for i in range(len(words) - 11):
            chunk = words[i:i+12]
            if all(w in BIP39_WORDS for w in chunk):
                # Likely seed phrase
                findings['seed_phrases'].append({
                    'path': rel_path,
                    'words': ' '.join(chunk[:3]) + ' ... ' + ' '.join(chunk[-3:]),
                    'count': len(chunk),
                    'warning': 'POTENTIAL SEED PHRASE — HANDLE WITH EXTREME CARE'
                })
                break  # One per file is enough
    
    return findings


def main():
    import argparse
    parser = argparse.ArgumentParser(description='CP8 Wallet Hunt Scanner')
    parser.add_argument('--root', default='/root/.openclaw/workspace', help='Scan root path')
    parser.add_argument('--output', default='wallet-hunt-report.json', help='Output JSON file')
    args = parser.parse_args()
    
    print(f"🔍 Scanning {args.root} for wallet artifacts...")
    findings = scan_workspace(args.root)
    
    report = {
        'scan_timestamp': datetime.now(timezone.utc).isoformat(),
        'hos_ground_truth': '63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320',
        'scanned_files': findings['scanned_files'],
        'findings': {
            'eth_addresses': findings['eth_addresses'],
            'btc_addresses': findings['btc_addresses'],
            'sol_addresses': findings['sol_addresses'],
            'potential_private_keys': findings['potential_pks'],
            'seed_phrases': findings['seed_phrases']
        },
        'summary': {
            'eth_found': len(findings['eth_addresses']),
            'btc_found': len(findings['btc_addresses']),
            'sol_found': len(findings['sol_addresses']),
            'pk_warnings': len(findings['potential_pks']),
            'seed_warnings': len(findings['seed_phrases'])
        }
    }
    
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"  SCAN COMPLETE")
    print(f"{'='*50}")
    print(f"  Files scanned: {findings['scanned_files']}")
    print(f"  ETH addresses: {len(findings['eth_addresses'])}")
    print(f"  BTC addresses: {len(findings['btc_addresses'])}")
    print(f"  SOL addresses: {len(findings['sol_addresses'])}")
    print(f"  PK warnings:   {len(findings['potential_pks'])}")
    print(f"  Seed warnings: {len(findings['seed_phrases'])}")
    print(f"  Report saved:  {args.output}")
    print(f"{'='*50}")
    
    if findings['potential_pks'] or findings['seed_phrases']:
        print("\n⚠️  POTENTIAL PRIVATE KEYS OR SEED PHRASES FOUND!")
        print("   Review report immediately. Do not share.")


if __name__ == '__main__':
    main()
