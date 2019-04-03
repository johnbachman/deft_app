import os
import json
import pickle

from flask import (
    Blueprint, request, render_template, session, url_for, redirect
    )


from .trips import trips_ground
from .locations import DATA_PATH


bp = Blueprint('ground', __name__)


@bp.route('/')
def main():
    return render_template('index.jinja2')


@bp.route('/longforms', methods=['POST'])
def load_longforms():
    shortform = request.form['shortform']
    session['shortform'] = shortform
    try:
        cutoff = float(request.form['cutoff'])
    except ValueError or TypeError:
        cutoff = 1.0
    try:
        data = _init_from_file(shortform)
    except ValueError:
        try:
            data = _init_with_trips(shortform, cutoff)
        except ValueError:
            return render_template('index.jinja2')
    (session['longforms'], session['scores'], session['names'],
     session['groundings']) = data
    data = list(zip(*data))
    return render_template('input.jinja2', data=data)


@bp.route('/input', methods=['POST'])
def add_groundings():
    name = request.form['name']
    grounding = request.form['grounding']
    if name and grounding:
        selected = request.form.getlist('select')
        for value in selected:
            index = int(value)-1
            session['names'][index] = name
            session['groundings'][index] = grounding
    data = list(zip(session['longforms'], session['scores'],
                    session['names'], session['groundings']))
    return render_template('input.jinja2', data=data)


@bp.route('/delete', methods=['POST'])
def delete_grounding():
    for key in request.form:
        if key.startswith('delete_'):
            id_ = key.partition('_')[-1]
            index = int(id_) - 1
            session['names'][index] = session['groundings'][index] = ''
            break
    data = list(zip(session['longforms'], session['scores'],
                    session['names'], session['groundings']))
    return render_template('input.jinja2', data=data)


@bp.route('/generate', methods=['POST'])
def generate_grounding_map():
    shortform = session['shortform']
    longforms = session['longforms']
    names = session['names']
    groundings = session['groundings']
    grounding_map = {longform: grounding if grounding else 'ungrounded'
                     for longform, grounding in zip(longforms, groundings)}
    names_map = {grounding: name for grounding, name in zip(groundings,
                                                            names)
                 if grounding and name}
    groundings_path = os.path.join(DATA_PATH, 'models', shortform)
    try:
        os.mkdir(groundings_path)
    except FileExistsError:
        pass
    with open(os.path.join(groundings_path,
                           f'{shortform}_grounding_map.json'), 'w') as f:
        json.dump(grounding_map, f)
    with open(os.path.join(groundings_path,
                           f'{shortform}_names.json'), 'w') as f:
        json.dump(names_map, f)
    return redirect(url_for('ground.main'))


def _init_with_trips(shortform, cutoff):
    longforms, scores = _load(shortform, cutoff)
    trips_groundings = [trips_ground(longform) for longform in longforms]
    names, groundings = zip(*trips_groundings)
    names = [name if name is not None else '' for name in names]
    groundings = [grounding if grounding is not None
                  else '' for grounding in groundings]
    return longforms, scores, names, groundings


def _init_from_file(shortform):
    longforms, scores = _load(shortform, 0)
    groundings_path = os.path.join(DATA_PATH, 'models', shortform)
    try:
        with open(os.path.join(groundings_path,
                               f'{shortform}_grounding_map.json'), 'r') as f:
            grounding_map = json.load(f)
        with open(os.path.join(groundings_path,
                               f'{shortform}_names.json'), 'r') as f:
            names = json.load(f)
    except EnvironmentError:
        raise ValueError
    groundings = [grounding_map.get(longform) for longform in longforms]
    groundings = ['' if grounding == 'ungrounded' else grounding
                  for grounding in groundings
                  if grounding is not None]
    names = [names.get(grounding) for grounding in groundings]
    names = [name if name is not None else '' for name in names]
    return longforms, scores, names, groundings


def _load(shortform, cutoff):
    longforms_path = os.path.join(DATA_PATH, 'longforms',
                                  f'{shortform}_longforms.pkl')
    try:
        with open(longforms_path, 'rb') as f:
            scored_longforms = pickle.load(f)
    except EnvironmentError:
        raise ValueError(f'data not currently available for shortform'
                         '{shortform}')
    longforms, scores = zip(*[(longform, score)
                              for longform, score in scored_longforms
                              if score > cutoff])
    return longforms, scores