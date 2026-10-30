CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -O1

test: test_analyse
	./test_analyse

test_analyse: test_analyse.cpp ../firmware/common/kabel_analyse.h
	$(CXX) $(CXXFLAGS) -o $@ test_analyse.cpp -lm

clean:
	rm -f test_analyse

.PHONY: test clean
