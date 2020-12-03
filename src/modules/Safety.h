#pragma once

#include <map>
#include <string>

#include "Module.h"
#include "../utils/strings.h"

class Safety : public Module
{
private:
    std::map<std::string, Module *> *modules;
    std::map<std::string, std::tuple<std::string, std::string, int>> conditions;

public:
    Safety(std::map<std::string, Module *> *modules) : Module("safety")
    {
        this->modules = modules;
    }

    void handleMsg(std::string msg)
    {
        std::string command = cut_first_word(msg);

        if (command == "set")
        {
            std::string key = cut_first_word(msg, '=');
            if (starts_with(key, "condition_"))
            {
                cut_first_word(key, '_');
                std::string module = cut_first_word(msg, ',');
                std::string trigger = cut_first_word(msg, ',');
                int state = atoi(cut_first_word(msg, ',').c_str());
                conditions[key] = std::make_tuple(module, trigger, state);
            }
            else
                printf("Unknown setting: %s\n", key.c_str());
        }
        else
        {
            printf("Unknown command: %s\n", command.c_str());
        }
    }

    bool check(Module *module)
    {
        for (auto const &item : conditions)
        {
            std::string name = std::get<0>(item.second);
            std::string trigger = std::get<1>(item.second);
            int state = std::get<2>(item.second);
            if ((name == "*" || name == module->name) && state != (*modules)[trigger]->state)
                return false;
        }
        return true;
    }
};
