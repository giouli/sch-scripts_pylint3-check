#!/usr/bin/env python3
# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
# pylint: disable= invalid-name, line-too-long
"""
Transliterate and transcript according to iso843:
http://www.sete.gr/files/Media/Egkyklioi/040707Latin-Greek.pdf
"""
import re
import unicodedata


_MAPPING_LETTERS = {
    'α' : 'a', 'ά' : 'á', 'β' : 'v', 'γ' : 'g', 'δ' : 'd', 'ε' : 'e',
    'έ' : 'é', 'ζ' : 'z', 'η' : 'i', 'ή' : 'í', 'θ' :'th', 'ι' : 'i',
    'ί' : 'í', 'ϊ' : 'ï', 'ΐ' : 'ḯ', 'κ' : 'k', 'λ' : 'l', 'μ' : 'm',
    'ν' : 'n', 'ξ' : 'x', 'ο' : 'o', 'ό' : 'ó', 'π' : 'p', 'ρ' : 'r',
    'σ' : 's', 'ς' : 's', 'τ' : 't', 'υ' : 'y', 'ύ' : 'ý', 'ϋ' : 'ÿ',
    'ΰ' : 'ÿ́', 'φ' : 'f', 'χ' :'ch', 'ψ' :'ps', 'ω' : 'o', 'ώ' : 'ó'}


_MAPPING_COMPINE_LETTERS = {
    'γγ':'ng', 'γξ':'nx', 'γχ':'nch'}


_RE_REG1 = 'α|ε|η'
_RE_REG2 = 'υ|ύ'
_RE_REG3 = 'β|γ|δ|ζ|λ|μ|ν|ρ|α|ά|ε|έ|η|ή|ι|ί|ϊ|ΐ|ο|ό|υ|ύ|ϋ|ΰ|ω|ώ'
_RE_REG4 = 'θ|κ|ξ|π|σ|τ|φ|χ|ψ'
_RE_REG5 = 'α|ά|ε|έ|ο|ό'
_RE_REG6 = 'υ|ύ|ϋ|ΰ'
_RE_REG7 = 'ο'
_RE_REG8 = 'ύ|υ'

_REG1 = '('+_RE_REG1.lower()+'|'+_RE_REG1.upper()+')('+_RE_REG2.lower()+'|'+_RE_REG2.upper()+')('+_RE_REG3.lower()+'|'+_RE_REG3.upper()+')'

_REG2 = '('+_RE_REG1.lower()+'|'+_RE_REG1.upper()+')('+_RE_REG2.lower()+'|'+_RE_REG2.upper()+')('+_RE_REG4.lower()+'|'+_RE_REG4.upper()+')'

_REG3 = '^μπ|^Μπ|^ΜΠ|^μΠ|μπ$|Μπ$|ΜΠ$|μΠ$'

_REG4 = '^PS|^TH|^CH'

_REG5 = '(γ|Γ)(γ|ξ|χ|Γ|Ξ|Χ)'

_REG6 = '('+_RE_REG5.lower()+'|'+_RE_REG5.upper()+')('+_RE_REG6.lower()+'|'+_RE_REG6.upper()+')'

_REG7 = '('+_RE_REG7.lower()+'|'+_RE_REG7.upper()+')('+_RE_REG8.lower()+'|'+_RE_REG8.upper()+')'


def transcript(string, accents=True):
    """Transcription of Greek characters into Latin characters"""
    string = re.sub(_REG1, replace_v, string)
    string = re.sub(_REG2, replace_f, string)
    string = re.sub(_REG3, replace_b, string)
    string = re.sub(_REG5, replace_g, string)
    string = re.sub(_REG7, replace_ou, string)

    letters = []
    for letter in string:
        if letter in _MAPPING_LETTERS:
            letters.append(_MAPPING_LETTERS[letter])
        elif letter.lower() in _MAPPING_LETTERS:
            letters.append(_MAPPING_LETTERS[letter.lower()].upper())
        else:
            letters.append(letter)

    string = ''.join(letters)

    if re.match(_REG4, string):
        string = string.replace(string[1], string[1].lower())

    if accents:
        return string
    else:
        return strip_accents(string)


def transliterate(string, accents=True):
    """Transliteration of Greek characters into Latin characters"""
    string = re.sub(_REG6, replace_ou, string)

    letters = []
    for letter in string:
        if letter in _MAPPING_LETTERS:
            letters.append(_MAPPING_LETTERS[letter])
        elif letter.lower() in _MAPPING_LETTERS:
            letters.append(_MAPPING_LETTERS[letter.lower()].upper())
        else:
            letters.append(letter)

    string = ''.join(letters)

    if re.match(_REG4, string):
        string = string.replace(string[1], string[1].lower())

    if accents:
        return string
    else:
        return strip_accents(string)


def replace_v(m):
    response = m.group(0)
    if m.group(2) == 'ύ' or m.group(2) == 'Ύ':
        if m.group(1) == 'α':
            response = response.replace(m.group(1), 'ά')
        elif m.group(1) == 'Α':
            response = response.replace(m.group(1), 'Ά')
        elif m.group(1) == 'ε':
            response = response.replace(m.group(1), 'έ')
        elif m.group(1) == 'Ε':
            response = response.replace(m.group(1), 'Έ')
        elif m.group(1) == 'η':
            response = response.replace(m.group(1), 'ή')
        elif m.group(1) == 'Η':
            response = response.replace(m.group(1), 'Ή')

    if m.group(2).islower():
        response = response.replace(m.group(2), 'v')
        return response
    else:
        response = response.replace(m.group(2), 'V')
        return response


def replace_f(m):
    response = m.group(0)
    if m.group(2) == 'ύ' or m.group(2) == 'Ύ':
        if m.group(1) == 'α':
            response = response.replace(m.group(1), 'ά')
        elif m.group(1) == 'Α':
            response = response.replace(m.group(1), 'Ά')
        elif m.group(1) == 'ε':
            response = response.replace(m.group(1), 'έ')
        elif m.group(1) == 'Ε':
            response = response.replace(m.group(1), 'Έ')
        elif m.group(1) == 'η':
            response = response.replace(m.group(1), 'ή')
        elif m.group(1) == 'Η':
            response = response.replace(m.group(1), 'Ή')

    if m.group(2).islower():
        response = response.replace(m.group(2), 'f')
        return response
    else:
        response = response.replace(m.group(2), 'F')
        return response


def replace_b(m):
    if m.group(0)[0].islower():
        return 'b'
    else:
        return 'B'


def replace_g(m):
    if m.group(0).islower():
        return _MAPPING_COMPINE_LETTERS[m.group(0)]
    elif m.group(0).isupper():
        return _MAPPING_COMPINE_LETTERS[m.group(0).lower()].upper()
    else:
        if m.group(0)[0].isupper() and m.group(0)[1].islower():
            response = _MAPPING_COMPINE_LETTERS[m.group(0).lower()]
            return response.replace(response[0], response[0].upper())
        elif m.group(0)[0].islower() and m.group(0)[1].isupper():
            response = _MAPPING_COMPINE_LETTERS[m.group(0).lower()]
            return response.replace(response[1], response[1].upper())


def replace_ou(m):
    response = m.group(0)
    if m.group(0)[1].islower():
        if m.group(0)[1] == 'ύ':
            response = response.replace(m.group(0)[1], 'ú')
            return response
        else:
            response = response.replace(m.group(0)[1], 'u')
            return response

    else:
        response = response.replace(m.group(0)[1], 'U')
        return response


def strip_accents(string):
    """Strippes from accent marks."""
    return ''.join((c for c in unicodedata.normalize('NFD', string) if unicodedata.category(c) != 'Mn'))
