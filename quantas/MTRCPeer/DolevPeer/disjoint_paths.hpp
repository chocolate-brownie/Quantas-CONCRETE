#include <iostream>
#include <vector>
#include <unordered_set>
#include <algorithm>
#include <functional>

using namespace std;


vector<unordered_set<long>> remove_src(const vector<unordered_set<long>>& sets, long src) {
    vector<unordered_set<long>> result = sets;
    for (auto& s : result) {
        s.erase(src);
    }
    return result;
}


bool are_disjoint(const unordered_set<long>& a, const unordered_set<long>& b) {
    const auto& small = (a.size() < b.size()) ? a : b;
    const auto& large = (a.size() < b.size()) ? b : a;
    for (long x : small) {
        if (large.find(x) != large.end()) {
            return false;
        }
    }
    return true;
}


bool are_disjoint(const vector<unordered_set<long>>& sets) {
    for (size_t i = 0; i < sets.size(); ++i) {
        for (size_t j = i + 1; j < sets.size(); ++j) {
            if (!are_disjoint(sets[i], sets[j])) {
                return false;
            }
        }
    }
    return true;
}

static void print_set(const unordered_set<long>& s) {
    cout << "{ ";
    for (long x : s) cout << x << " ";
    cout << "}";
}

static void print_list_sets(const vector<unordered_set<long>>& sets) {
    cout << "[\n";
    for (const auto& s : sets) {
        cout << "  ";
        print_set(s);
        cout << "\n";
    }
    cout << "]\n";
}

bool k_disjoint(const vector<unordered_set<long>> &vs, int k) {
    if (k <= 0) return true;
    if (static_cast<int>(vs.size()) < k) return false;

    unordered_set<long> used;
    vector<int> selected_indices;

    function<bool(int, int)> dfs = [&](int start, int chosen) -> bool {
        if (chosen == k) {
            /*cout << "\n\nFound " << k << " disjoint sets:\n";
            for (int idx : selected_indices) {
                cout << "  idx " << idx << " = ";
                print_set(vs[idx]);
                cout << "\n";
            }*/
            return true;
        }

        int remaining = k - chosen;
        for (int i = start; i <= static_cast<int>(vs.size()) - remaining; ++i) {
            bool conflict = false;
            for (long x : vs[i]) {
                if (used.find(x) != used.end()) {
                    conflict = true;
                    break;
                }
            }
            if (conflict) continue;

            selected_indices.push_back(i);
            for (long x : vs[i]) used.insert(x);

            if (dfs(i + 1, chosen + 1)) return true;

            for (long x : vs[i]) used.erase(x);
            selected_indices.pop_back();
        }
        return false;
    };

    return dfs(0, 0);
}


bool contained_in(const vector<unordered_set<long>>& sets, const unordered_set<long>& candidate){

    for (const auto& s : sets){
        if (s.size() > candidate.size()) continue;
        
        bool contained = true;
        for (long x : s){
            if (candidate.find(x) == candidate.end()){
                contained = false;
                break;
            }
        }
        if (contained) return true;
    }
    return false;

}


bool is_subset(const unordered_set<long>& a, const unordered_set<long>& b) {
    if (a.size() > b.size()) return false;
    for (long x : a) {
        if (b.find(x) == b.end()) {
            return false;
        }
    }
    return true;
}

vector<unordered_set<long>> remove_unnecessary_paths(const vector<unordered_set<long>>& sets){
    
    int max_length = 0;
    for (const auto& set : sets){
        if (set.size() > max_length) max_length = set.size();
    }
    

    // make a deep copy of sets but ordered by size
    vector<unordered_set<long>> copy_sets = {};
    for (int i = 0; i <= max_length; ++i){
        for (const auto& set : sets){
            if (set.size() != i) continue;
            unordered_set<long> tmp = {};
            for (long x : set) tmp.insert(x);
            copy_sets.push_back(tmp);
        }
    }

    
    vector<unordered_set<long>> result = {};
    int i = 0;
    while (i < static_cast<int>(copy_sets.size())){

        // remove all sets for which copy_sets[i] is a subset
        int j = i+1;
        while (j < static_cast<int>(copy_sets.size())){
            if (is_subset(copy_sets[i], copy_sets[j])){
                copy_sets.erase(copy_sets.begin() + j);
            }
            else j++;
        }
        result.push_back(copy_sets[i]);
        i++;
    }
    return result;
}
