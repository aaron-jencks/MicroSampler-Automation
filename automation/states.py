from enum import Enum


class LoopState(Enum):
    HYPOTHESIS = 0
    CODE_GEN = 1
    SIMULATION = 2
    ANALYSIS = 3
    SUMMARIZATION = 4
    CONCLUSION = 5
