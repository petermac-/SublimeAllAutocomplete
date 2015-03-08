# Extends Sublime Text autocompletion to find matches in all open
# files. By default, Sublime only considers words from the current file.

import sublime_plugin
import sublime
import re
import time

# limits to prevent bogging down the system
MIN_WORD_SIZE = 3
MAX_WORD_SIZE = 50

MAX_VIEWS = 20
MAX_WORDS_PER_VIEW = 100
MAX_FIX_TIME_SECS_PER_VIEW = 0.01

#Change this variable to True to se debug output
DEBUG = False

class SubLimeallautocomplete(sublime_plugin.EventListener):
    #default settings
    dash_hack_sytaxes = ["source.scss","source.sass","source.css"]
    return_nothing_on_empty = True
    not_search_in_current = True

    def __init__(self):
        if DEBUG: print("initializing Sublimeallautocomplete(SAA) plugin")

    #Loading settings when view is activated
    def on_activated(self,view):
        if DEBUG: print("\nActivating SAA for view",view)
        self.plugin_settings = sublime.load_settings('SublimeAllAutocomplete.sublime-settings')

        dash_hack_sytaxes = self.plugin_settings.get('apply_with_dash_hack_syntaxes')
        return_nothing_on_empty = self.plugin_settings.get('return_nothing_on_empty_prefix')
        not_search_in_current = self.plugin_settings.get('do_not_search_in_current_view')
        if DEBUG: print("SAA: user settings:\n dash_hack_sytaxes:{0}\n return_nothing_on_empty:{1}\n not_search_in_current:{2}".format(dash_hack_sytaxes,return_nothing_on_empty,not_search_in_current))

        #using default settings
        if dash_hack_sytaxes != None:
            self.dash_hack_sytaxes = dash_hack_sytaxes

        if return_nothing_on_empty != None:
            self.return_nothing_on_empty = return_nothing_on_empty

        if not_search_in_current != None:
            self.not_search_in_current = not_search_in_current

        if DEBUG: print("SAA: Merged settings:\n dash_hack_sytaxes:{0}\n return_nothing_on_empty:{1}\n not_search_in_current:{2}\n".format(self.dash_hack_sytaxes,self.return_nothing_on_empty,self.not_search_in_current))

    def on_query_completions(self, view, prefix, locations):

        if DEBUG: print("SAA: running completion query '{0}'".format(prefix))
        words = []

        # Limit number of views but always include the active view. This
        # view goes first to prioritize matches close to cursor position.
        other_views = [v for v in sublime.active_window().views() if v.id != view.id]
        views = [view] + other_views
        views = views[0:MAX_VIEWS]
        if DEBUG: print("SAA: views to process {0}".format(views))

        if self.return_nothing_on_empty:
            if not prefix:
                if DEBUG: print("SAA: returning nothing on empty query")
                return words;

        for v in views:
            view_words = []
            location = 0
            # Hacking around dash auto-completion bug
            # https://github.com/alienhard/Sublimeallautocomplete/issues/18

            # Sublime probably already works fine with suggestions from current view
            if self.not_search_in_current and v.id == view.id:
                continue

            if len(locations) > 0 and v.id == view.id:
                location = locations[0]

            if self.is_need_to_be_hacked(v, self.dash_hack_sytaxes):
                # apply hack for css and sass only
                view_words = self.extract_completions_wdash(v,prefix);
            else:
                view_words = v.extract_completions(prefix, location)

            view_words = self.filter_words(view_words)
            view_words = self.fix_truncation(v, view_words)
            words += view_words

        words = self.without_duplicates(words)
        if DEBUG: print("SAA: {0} words found".format(len(words)))

        matches = [(w, w.replace('$', '\\$')) for w in words]
        return matches

    def is_need_to_be_hacked(self, v, dash_hack_sytaxes):
        for syntax in dash_hack_sytaxes:
            if v.scope_name(0).find(syntax) >= 0:
                return True
        return False

    # extract auto-completions with dash
    # see https://github.com/alienhard/Sublimeallautocomplete/issues/18
    def extract_completions_wdash(self, v,prefix):
        if DEBUG: print("SAA: extracting words with dashes")
        word_regions = v.find_all(prefix,0)
        words = []

        for wr in word_regions:
            word = v.substr(v.word(wr))
            words.append(word)

        if DEBUG: print("SAA: {0} dash-words found".format(len(words)))

        return words

    def filter_words(self, words):
        words = words[0:MAX_WORDS_PER_VIEW]
        return [w for w in words if MIN_WORD_SIZE <= len(w) <= MAX_WORD_SIZE]

    # keeps first instance of every word and retains the original order
    # (n^2 but should not be a problem as len(words) <= MAX_VIEWS*MAX_WORDS_PER_VIEW)
    def without_duplicates(self, words):
        if DEBUG: print("SAA: cleaning duplicates")
        result = []
        for w in words:
            if w not in result:
                result.append(w)
        return result


    # Ugly workaround for truncation bug in Sublime when using view.extract_completions()
    # in some types of files.
    def fix_truncation(self, view, words):
        if DEBUG: print("SAA: fixing turncation")
        fixed_words = []
        start_time = time.time()

        for i, w in enumerate(words):
            #The word is truncated if and only if it cannot be found with a word boundary before and after

            # this fails to match strings with trailing non-alpha chars, like
            # 'foo?' or 'bar!', which are common for instance in Ruby.
            match = view.find(r'\b' + re.escape(w) + r'\b', 0)
            truncated = self.is_empty_match(match)
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

    def is_empty_match(self, match):
        if sublime.version() >= '3000':
            return match.empty()
        else:
            return match is None
