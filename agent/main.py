"""Direct-run entry point for the agent (also the PyInstaller build target).

Equivalent to the installed `datasentinel` console script, kept as a plain
script since PyInstaller packages a script entry point more predictably than a
package's `[project.scripts]` shim.
"""

from datasentinel_agent.cli.main import main

if __name__ == "__main__":
    main()
