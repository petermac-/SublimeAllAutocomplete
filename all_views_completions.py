# Extends Sublime Text autocompletion to find matches in all open
# files. By default, Sublime only considers words from the current file.

import sublime_plugin
import sublime
import re
import time

# limits to prevent bogging down the system
MIN_WORD_SIZE = 3
MAX_WORD_SIZE = 30

MAX_VIEWS = 20
MAX_WORDS_PER_VIEW = 100
MAX_FIX_TIME_SECS_PER_VIEW = 0.01

class AllAutocomplete(sublime_plugin.EventListener):

    #default settings
    dash_hack_sytaxes = ["source.sass","source.css"]
    return_nothing_on_empty = True

    def __init__(self):
        dash_hack_sytaxes = sublime.load_settings('AllAutocomplete.sublime-settings').get('apply_with_dash_hack_syntaxes')
        return_nothing_on_empty = sublime.load_settings('AllAutocomplete.sublime-settings').get('return_nothing_on_empty_prefix')
        
        #using default settings
        if dash_hack_sytaxes != None:                        
            self.dash_hack_sytaxes = dash_hack_sytaxes

        if return_nothing_on_empty != None:
            self.return_nothing_on_empty = return_nothing_on_empty

    def on_query_completions(self, view, prefix, locations):        
        words = []

        # Limit number of views but always include the active view. This
        # view goes first to prioritize matches close to cursor position.
        other_views = [v for v in sublime.active_window().views() if v.id != view.id]
        views = [view] + other_views
        views = views[0:MAX_VIEWS]

        if self.return_nothing_on_empty:
            if not prefix:
                return words;

        for v in views:
            # Hacking around dash auto-completion bug
            # https://github.com/alienhard/SublimeAllAutocomplete/issues/18
            if is_need_to_be_hacked(v, self.dash_hack_sytaxes):
                # apply hack for css and sass only
                if len(locations) > 0 and v.id == view.id:
                    view_words = extract_completions_wdash(v,prefix,locations[0])
                else:
                    view_words = extract_completions_wdash(v,prefix);
            else:
                if len(locations) > 0 and v.id == view.id:
                    view_words = v.extract_completions(prefix, locations[0])
                else:
                    view_words = v.extract_completions(prefix)

            view_words = filter_words(view_words)
            view_words = fix_truncation(v, view_words)
            words += view_words

        words = without_duplicates(words)
        matches = [(w, w.replace('$', '\\$')) for w in words]
        return matches

def is_need_to_be_hacked(v, dash_hack_sytaxes):
    for syntax in dash_hack_sytaxes:
        if v.scope_name(0).find(syntax) >= 0:
            return True
    return False

# extract auto-completions with dash
# see https://github.com/alienhard/SublimeAllAutocomplete/issues/18
def extract_completions_wdash(v,prefix,location=0):    
    word_regions = v.find_all(prefix,0)
    words = []

    for wr in word_regions:
        word = v.substr(v.word(wr))        
        words.append(word)

    return words

def filter_words(words):
    words = words[0:MAX_WORDS_PER_VIEW]
    return [w for w in words if MIN_WORD_SIZE <= len(w) <= MAX_WORD_SIZE]

# keeps first instance of every word and retains the original order
# (n^2 but should not be a problem as len(words) <= MAX_VIEWS*MAX_WORDS_PER_VIEW)
def without_duplicates(words):
    result = []
    for w in words:
        if w not in result:
            result.append(w)
    return result


# Ugly workaround for truncation bug in Sublime when using view.extract_completions()
# in some types of files.
def fix_truncation(view, words):
    fixed_words = []
    start_time = time.time()

    for i, w in enumerate(words):
        #The word is truncated if and only if it cannot be found with a word boundary before and after

        # this fails to match strings with trailing non-alpha chars, like
        # 'foo?' or 'bar!', which are common for instance in Ruby.
        match = view.find(r'\b' + re.escape(w) + r'\b', 0)
        truncated = is_empty_match(match)
        if truncated:
            #Truncation is always by a single character, so we extend the word by one word character before a word boundary
            extended_words = []
            view.find_all(r'\b' + re.escape(w) + r'\w\b', 0, "$0", extended_words)
            if len(extended_words) > 0:
                fixed_words += extended_words
            else:
                # to compensate for the missing match problem mentioned above, just
                # use the old word if we didn't find any extended matches
                fixed_words.append(w)
        else:
            #Pass through non-truncated words
            fixed_words.append(w)

        # if too much time is spent in here, bail out,
        # and don't bother fixing the remaining words
        if time.time() - start_time > MAX_FIX_TIME_SECS_PER_VIEW:
            return fixed_words + words[i+1:]

    return fixed_words

if sublime.version() >= '3000':
  def is_empty_match(match):
    return match.empty()
else:
  def is_empty_match(match):
    return match is None
