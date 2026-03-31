How can I make a system that allows the agent to execute actions like codex? Maybe I should add a CRUD interface that allows the user to create their own actions and define them with callbacks at run-time. Then it would have a system for formatting the actions into a form of documentation that can then be inserted into the prompt. Could we generate the documentation automatically? Maybe, but not really, it'd likely need some kind of helper string or something to define the functionality of the tool. We can then just expose these as a list of tools to the prompt, however I think we'd still have to define them. I wonder if we would want to add some kind of way to discern between source and other files in the prompt template. Something liek `[[prompt:some/prompt/file.txt]]` and `[[source:some/source/file.txt]]`. I think that would be best, but how does it interact with the auto-generated documentation for the actions. I think it's still necessary, so let's do that.

1. We make a CRUD system for creating and defining actions at run-time.
2. We make a system for auto-generating documentation for the actions
3. We supply them as tools to the llm
4. Add additional syntax to the template so that we can handle various types of prefixes during parsing.

3/31/2026

I'm almost done getting the actions integrated into the governor, I just need to update the client to actually allow the use of the template tools and then get the prompt reconfigured and then re-do the loop in the governor main loop. Shouldn't take more than a few hours.