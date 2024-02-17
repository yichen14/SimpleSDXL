import os
import re
import json
import math
import gradio as gr
import enhanced.translator as translator

from modules.util import get_files_from_folder
from args_manager import args

wildcards_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../wildcards/'))
wildcards_max_bfs_depth = 64

wildcards = {}
wildcards_list = {}
wildcards_translation = {}
wildcards_template = {}
wildcards_weight_range = {}

array_regex = re.compile(r'\[([\w\.\s,:-]+)\]')
tag_regex1 = re.compile(r'([\s\w,-]+)')
tag_regex2 = re.compile(r'__([\w-]+)__')
tag_regex3 = re.compile(r'__([\w-]+)__:([\d]+)')
tag_regex4 = re.compile(r'__([\w-]+)__:([RL]){1}([\d]*)')
tag_regex5 = re.compile(r'__([\w-]+)__:([RL]){1}([\d]*):([\d]+)')
wildcard_regex = re.compile(r'-([\w-]+)-')

def set_wildcard_path_list(name, list_value):
    global wildcards_list
    if name in wildcards_list.keys():
        if list_value not in wildcards_list[name]:
            wildcards_list[name].append(list_value)
    else:
        wildcards_list.update({name: [list_value]})

def get_wildcards_samples(path="root"):
    global wildcards_path, wildcards, wildcards_list, wildcards_translation, wildcards_template, wildcards_weight_range, wildcard_regex

    if len(wildcards.keys()) == 0:
        wildcards_list_all = sorted([f[:-4] for f in get_files_from_folder(wildcards_path, ['.txt'], None)])
        wildcards_list_all = [x for x in wildcards_list_all if '_' not in x]
        #print(f'wildcards_list:{wildcards_list_all}')
        for wildcard in wildcards_list_all:
            words = open(os.path.join(wildcards_path, f'{wildcard}.txt'), encoding='utf-8').read().splitlines()
            words = [x.split('?')[0] for x in words if x != '' and not wildcard_regex.findall(x)]
            words = [x.split(';')[0] for x in words]

            templates = [x for x in words if ':' in x]  #  word:template:weight_range
            for line in templates:
                parts = line.split(";")
                word = parts[0]
                template = parts[1]
                weight_range = ''
                if len(parts)>2:
                    weight_range = parts[2]
                if word is None or word == '':
                    wildcards_template.update({wildcard: template})
                    if len(weight_range.strip())>0:
                        wildcards_weight_range.update({wildcard: weight_range})
                else:
                    wildcards_template({wildcard+"/"+word: template})
                    if len(weight_range.strip())>0:
                        wildcards_weight_range.update({wildcard+"/"+word: weight_range})
            words = [x.split(";")[0] for x in words]
            wildcards.update({wildcard: words})
            wildcard_path = wildcard.split("/")
            if len(wildcard_path)==1:
                set_wildcard_path_list("root", wildcard_path[0])
            elif len(wildcard_path)==2:
                set_wildcard_path_list(wildcard_path[0], wildcard_path[1])
                #set_wildcard_path_list("root", wildcard_path[0])
            elif len(wildcard_path)==3:
                set_wildcard_path_list(wildcard_path[0]+'/'+wildcard_path[1], wildcard_path[2])
                set_wildcard_path_list(wildcard_path[0], wildcard_path[1])
                #set_wildcard_path_list("root", wildcard_path[0])
            else:
                print(f'[Wildcards] The level of wildcards is too depth: {wildcards_path}.')
        #print(f'wildcards_list:{wildcards_list}')
        print(f'[Wildcards] Load {len(wildcards_list_all)} wildcards from {wildcards_path}.')
    if args.language=='cn':
        if len(wildcards_translation.keys())==0:
            wildcards_translation_file = os.path.join(wildcards_path, 'cn.json')
            if os.path.exists(wildcards_translation_file):
                with open(wildcards_translation_file, "r", encoding="utf-8") as json_file:
                    wildcards_translation.update(json.load(json_file))
                update_flag = False
                for x in wildcards_list[path]:
                    if 'list/'+x not in wildcards_translation.keys():
                        wildcards_translation.update({f'list/{x}': translator.convert(x, 'Big Model', 'cn')})
                        update_flag = True
                if update_flag:
                    with open(wildcards_translation_file, "w", encoding="utf-8") as json_file:
                        json.dump(wildcards_translation, json_file)
            else:
                for wildcard in wildcards_list["root"]:
                    wildcards_translation.update({f'list/{wildcard}': translator.convert(wildcard, 'Big Model', 'cn')})
                #for wildcard in wildcards.keys():
                #    for word in wildcards[wildcard]:
                #        wildcards_translation.update({f'word/{wildcard}/{word}': translator.convert(word, 'Big Model', 'cn')})
                with open(wildcards_translation_file, "w", encoding="utf-8") as json_file:
                    json.dump(wildcards_translation, json_file)
        return [[x+'|'+wildcards_translation['list/'+x]] for x in wildcards_list[path]]

    return [[x] for x in wildcards_list[path]]

def get_words_of_wildcard_samples(wildcard="root"):
    global wildcards, wildcards_list

    if wildcard == "root":
        return [[x] for x in wildcards[wildcards_list[wildcard][0]]]
    return [[x] for x in wildcards[wildcard]]

def get_words_with_wildcard(wildcard, rng, method='R', number=1, start_at=1):
    global wildcards

    words = wildcards[wildcard]
    words_result = []
    number0 = number
    if method=='L':
        if number == 0:
            words_result = words
        else:
            if number < 0:
                number = 1
            start = start_at - 1
            if number > len(words):
                number = len(words)
            if (start + number)>len(words):
                words_result = words[start:] + words[:start + number - len(words)]
            else:
                words_result = words[start:start + number]
    else:
        if number < 1:
            number = 1
        if number > len(words):
            number = len(words)
        for i in range(number):
            words_result.append(rng.choice(words))
    print(f'[Wildcards] Get words from wildcard:__{wildcard}__, method:{method}, number:{number}, start_at:{start_at}, result:{words_result}')
    return words_result


def compile_arrays(text, rng):
    global array_regex, tag_regex1, tag_regex2, tag_regex3, tag_regex4, tag_regex5

    tag_arrays = array_regex.findall(text)
    if len(tag_arrays)==0:
        return text, [], 0
    arrays = []
    mult = 1
    for tag in tag_arrays:
        colon_counter = tag.count(':')
        wildcard = ''
        number = 1
        method = 'R'
        start_at = 1
        if colon_counter == 2:
            parts = tag_regex5.findall(tag)
            if parts:
                parts = list(parts[0])
                wildcard = parts[0]
                method = parts[1]
                if parts[2]:
                    number = int(parts[2])
                start_at = int(parts[3])
        elif colon_counter == 1:
            parts = tag_regex3.findall(tag)
            if parts:
                parts = list(parts[0])
                wildcard = parts[0]
                number = int(parts[1])
            else:
                parts = tag_regex4.findall(tag)
                if parts:
                    parts = list(parts[0])
                    wildcard = parts[0]
                    method = parts[1]
                    if parts[2]:
                        number = int(parts[2])
        elif colon_counter == 0:
            parts = tag_regex2.findall(tag)
            if parts:
                wildcard = parts[0]
            else:
                parts = tag_regex1.findall(tag)
                if parts:
                    words = parts[0].split(',')
                    words = [x.strip() for x in words]
                    text = text.replace(tag, ','.join(words))
                    arrays.append(words)
                    mult *= len(words)
                    continue
        words = get_words_with_wildcard(wildcard, rng, method, number, start_at)
        text = text.replace(tag, ','.join(words))
        arrays.append(words)
        mult *= len(words)
    print(f'[Wildcards] Copmile text in prompt to arrays: {text} -> arrays:{arrays}, mult:{mult}')
    return text, arrays, mult 


def get_words(arrays, totalMult, index):
    if(len(arrays) == 1):
        return [arrays[0][index]]
    else:
        words = arrays[0]
        word = words[index % len(words)]
        index -= index % len(words)
        index /= len(words)
        index = math.floor(index)
        return [word] + get_words(arrays[1:], math.floor(totalMult/len(words)), index)


def apply_arrays(text, index, arrays, mult):
    if len(arrays) == 0:
        return text

    index %= mult
    chosen_words = get_words(arrays, mult, index)

    i = 0
    for arr in arrays:
        text = text.replace(f'[{",".join(arr)}]', chosen_words[i], 1)
        i = i+1

    return text


def apply_wildcards(wildcard_text, rng, directory=wildcards_path):
    global tag_regex2, wildcards

    for _ in range(wildcards_max_bfs_depth):
        placeholders = tag_regex2.findall(wildcard_text)
        if len(placeholders) == 0:
            return wildcard_text

        print(f'[Wildcards] processing: {wildcard_text}')
        for placeholder in placeholders:
            try:
                words = wildcards[placeholder]
                assert len(words) > 0
                wildcard_text = wildcard_text.replace(f'__{placeholder}__', rng.choice(words), 1)
            except:
                print(f'[Wildcards] Warning: {placeholder}.txt missing or empty. '
                      f'Using "{placeholder}" as a normal word.')
                wildcard_text = wildcard_text.replace(f'__{placeholder}__', placeholder)
            print(f'[Wildcards] {wildcard_text}')

    print(f'[Wildcards] BFS stack overflow. Current text: {wildcard_text}')
    return wildcard_text


def add_wildcards_and_array_to_prompt(wildcard, prompt, state_params):
    global wildcards, wildcards_list

    wildcard = wildcard[0].split('|')[0]
    state_params.update({"wildcard_in_wildcards": wildcard})
    if prompt[-1]=='[':
        state_params["array_wildcards_mode"] = '['
        prompt = prompt[:-1]
    elif prompt[-1]=='_':
        state_params["array_wildcards_mode"] = '_'
        if len(prompt)==1 or len(prompt)>2 and prompt[-2]!='_':
            prompt = prompt[:-1]
    
    if state_params["array_wildcards_mode"] == '[':
        new_tag = f'[__{wildcard}__]'
    else:
        new_tag = f'__{wildcard}__'
    prompt = f'{prompt.strip()} {new_tag}'
    return gr.update(value=prompt), gr.Dataset.update(label=f'{wildcard}:', samples=get_words_of_wildcard_samples(wildcard)), gr.update(open=True)