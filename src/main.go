package main

import (
	"flag"
	"fmt"
	"strings"
	"strconv"
	"sync"
	"time"

	"os"
	"os/exec"
	"syscall"
	"path/filepath"

	"bufio"
	"io"
	"io/ioutil"

	"gopkg.in/yaml.v2"
	"encoding/json"
)

// RepoFile sucks
type RepoFile struct {
	Repos  map[string]repoConfig
	Config config
}
type args struct {
	branch         bool
	csv            bool
	csvSep         string
	command        string
	path           string
	name           string
	generateConfig bool
	njobs          int
	noFetch        bool
	repo           string
	listNames      bool
	listPaths      bool
	getDir         string
	configFile     string
	recent         bool
	days           int
	all            bool
	noignore       bool
	subcommand     string
	behind         bool
	foreach        string
	outputFormat   string
	posargs        []string
}


func getArgs() args {

	var a args

	flag.Usage = func(){
		fmt.Printf("Repos is a tool for listing the states of multiple local repos.  See man repos for more information\n\nUsage:\n\n\trepos [options]\n\nOptions:\n")
		flag.PrintDefaults()
	}
	a.command = flag.Arg(0)

	flag.StringVar(&a.foreach, "foreach", "", "Do a command on every repo")
	flag.StringVar(&a.path, "path", "", "Specify a single repo to give info for")
	flag.BoolVar(&a.generateConfig, "generate-config", false, "Look for git repos in PWD and generate ~/.config/repos.yml file content on STDOUT.")
	flag.IntVar(&a.njobs, "j", 1, "Number of concurrent repos to do")
	flag.BoolVar(&a.branch, "branch", false, "Print the current branch")
	flag.BoolVar(&a.csv, "csv", false, "Output in CSV format in certain contexts")
	flag.StringVar(&a.csvSep, "csv-sep", ",", "Separator to use for CSV")
	flag.BoolVar(&a.noFetch, "no-fetch", false, "Disable auto-fetching")
	flag.StringVar(&a.repo, "r", "", "Start new shell with cleared environment in repo")
	flag.BoolVar(&a.listNames, "list-names", false, "Output list of names for autocomplete")
	flag.BoolVar(&a.listPaths, "list-paths", false, "Output list of paths for autocomplete")
	flag.BoolVar(&a.behind, "behind", false, "List paths only shows path that are behind")
	flag.StringVar(&a.getDir, "get-dir", "", "Get directory of repo on STDOUT")
	flag.StringVar(&a.configFile, "F", "", "Use a different config file that ~/.config/repos.yml")
	flag.BoolVar(&a.recent, "recent", false, "Show today and yesterday's commits for all repos")
	flag.IntVar(&a.days, "days", 1, "Go back more than one day before yesterday when using option -recent")
	flag.BoolVar(&a.all, "all", false, "Print all repos instead of just the onse with modifications")
	flag.BoolVar(&a.noignore, "noignore", false, "Disregard the ignore flag on repos")
	flag.StringVar(&a.outputFormat, "output-format", "ansi", "Output format, one of 'ansi', 'text', 'json'")

	flag.Parse()
	a.posargs = flag.Args()

	return a
}

type config struct {
	Color    bool `yaml:"color"`
	Defaults repoConfig `yaml:"defaults"`
	RepoDir  string `yaml:"repo-dir"`
	RepoDirScheme RepoDirScheme `yaml:"repo-dir-scheme"`
}

type RepoDirScheme string

const (
	RepoDirSchemeFlat = "flat"
	RepoDirSchemeUrl = "url"
	RepoDirSchemeNone = "none"
)

type repoConfig struct {
	Path      string
	Name      string
	ShortName string
	Fetch     bool
	Comment   string
	Remote    string
	Ignore    bool
}

type repoInfo struct {
	Config repoConfig
	State  repoState
}

type repoState struct {
	Dirty               bool
	UntrackedFiles      int
	UntrackedDirs       int
	TimeSinceLastCommit time.Duration
	RemoteState         RemoteState
	StagedChanges       bool
	Files               int
	Insertions          int
	Deletions           int
	StagedInsertions    int
	StagedDeletions     int
	StagedFiles         int
	CurrentBranch       string // TODO Maybe there are some async concerns with this
}

type repos []repoConfig

func (r repoConfig) gitCommand(args ...string) *exec.Cmd {
	// time.Sleep(time.Millisecond * 500)
	args2 := []string{"-c", "color.ui=always"}
	args2 = append(args2, args...)
	cmd := exec.Command("git", args2...)
	cmd.Stderr = os.Stderr
	cmd.Dir = r.Path
	return cmd
}

func (r repoConfig) command(name string, args ...string) *exec.Cmd {
	cmd := exec.Command(name, args...)
	cmd.Dir = r.Path
	return cmd
}

func (r *repoConfig) bashCommand(code string) *exec.Cmd {
	cmd := exec.Command("bash", "-o", "pipefail", "-c", code)
	cmd.Stderr = os.Stderr
	cmd.Dir = r.Path
	return cmd
}

func (r *repoConfig) hasUnstagedChanges() (bool, error) {
	cmd := r.gitCommand("diff", "--no-ext-diff", "--quiet", "--exit-code")
	_ = cmd.Run()
	if cmd.ProcessState == nil {
		return false, fmt.Errorf("Failed to run command %v for repo %v", cmd, r)
	}
	return !cmd.ProcessState.Success(), nil
}

func (r *repoConfig) hasStagedChanges() (bool, error) {
	cmd := r.gitCommand("diff", "--staged", "--no-ext-diff", "--quiet", "--exit-code")
	_ = cmd.Run()
	if cmd.ProcessState == nil {
		return false, fmt.Errorf("Failed to run command %v for repo %v", cmd, r)
	}
	return !cmd.ProcessState.Success(), nil
}

type RemoteState struct {
	Ahead int
	Behind int
}

func (r *repoConfig) getRemoteState() (RemoteState, error) {
	cmd := r.gitCommand("rev-list", "--count", "--left-right", "@{upstream}...HEAD")
	cmd.Stderr = nil
	out, err := cmd.Output()
	var rs RemoteState
	fmt.Sscanf(string(out), "%d\t%d", &rs.Behind, &rs.Ahead)

	if err != nil {
		return rs, nil
	}

	return rs, nil
}

func (r *repoConfig) hasUntrackedFiles() (int, int, error) {
	cmd := r.gitCommand("ls-files", r.Path, "--others", "--exclude-standard", "--directory", "--no-empty-directory")
	out, err := cmd.Output()
	if err != nil {
		return 0, 0, fmt.Errorf("Could not run git command for repo '%s' : %v", r.Path, err)
	}
	/*
	 * Split(s,"\n") on an empty string produces
	 * a list with a single element which is the empty string
	 * so we have to check for empty string first otherwise
	 * repos with zero untracked files would return 1.
	 */
	if len(out) == 0 {
		return 0, 0, nil
	}

	files := strings.Split(strings.TrimSpace(string(out)), "\n")
	var nbDirs int = 0
	var nbFiles int = 0
	for _, f := range files {
		if strings.HasSuffix(f, "/") {
			nbDirs += 1
		} else {
			nbFiles += 1
		}
	}
	return nbDirs, nbFiles, nil
}

func (r *repoConfig) getInsertionsAndDeletions(staged bool) (int, int, int, error) {
	args := []string{"diff", "--numstat"}
	if staged {
		args = append(args, "--staged")
	}
	cmd := r.gitCommand(args...)
	out, err := cmd.StdoutPipe()
	cmd.Start()
	if err != nil {
		panic(err)
	}
	scanner := bufio.NewScanner(out)
	ins := 0
	del := 0
	files := 0
	for scanner.Scan() {
		line := scanner.Text()
		words := strings.Split(line, "\t")
		if len(words) != 3 {
			return 0, 0, 0, fmt.Errorf("number of words != 3: %s", line)
		}
		if words[0] == "-" {
			ins += 1
		} else {
			lineIns, err := strconv.Atoi(words[0])
			if err != nil {
				return 0, 0, 0, err
			}
			ins += lineIns
		}

		if words[1] == "-" {
			del += 1
		} else {
			lineDel, err := strconv.Atoi(words[1])
			if err != nil {
				return 0, 0, 0, err
			}
			del += lineDel
		}
		files += 1
	}
	return files, ins, del, nil
}

func dumpDatabase(filename string, database []*repoInfo) {
	repos := make(map[string]repoConfig, len(database))
	for _, ri := range database {
		repos[ri.Config.Name] = ri.Config
	}
	repoFile := RepoFile{
		Repos: repos,
	}
	yamlOut, err := yaml.Marshal(&repoFile)
	if err != nil {
		panic(err)
	}
	ioutil.WriteFile(filename, yamlOut, 0644)
}

func showRecentCommits(database []*repoInfo, args args) error {
	for _, ri := range database {
		if !args.noignore && ri.Config.Ignore {
			continue
		}
		cmd := ri.Config.gitCommand("recent", "--all", "-d", fmt.Sprintf("%d", (args.days)))
		out, err := cmd.Output()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Could not get recent commits for %s: %v\n", ri.Config.Path, err)
		}
		if len(out) > 0 {
			fmt.Fprintf(os.Stderr, "\033[1;4;35mRecent commits on all branches for %s\033[0m\n", ri.Config.Path)
			fmt.Fprint(os.Stderr, string(out))
		}
	}
	return nil
}

func readDatabase(filename string) ([]*repoInfo, *config, error) {
	repoFile := RepoFile{}

	yml, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, nil, err
	}
	yaml.Unmarshal(yml, &repoFile)

	database := make([]*repoInfo, 0, len(repoFile.Repos)+8)
	for name, rp := range repoFile.Repos {
		rp.Name = name
		ri := repoInfo{
			Config: rp,
		}
		database = append(database, &ri)
	}
	return database, &repoFile.Config, nil
}

func (r repoConfig) fetch() error {
	cmd := r.gitCommand("fetch")
	cmd.Stderr = nil
	_ = cmd.Run()
	if cmd.ProcessState == nil {
		return fmt.Errorf("error encountered when attempting to fetch '%s'", r.Path)
	}
	if ! cmd.ProcessState.Success() {
		return fmt.Errorf("fetch command failed for repo '%s' : %v", r.Path, cmd.ProcessState.ExitCode())
	}
	return nil
}

func (r repoConfig) getState(a args) (repoState, error) {

	state := repoState{}
	var err error

	state.TimeSinceLastCommit, err = r.getTimeSinceLastCommit()
	if err != nil {
		return state, err
	}

	// state.Dirty, err = r.hasUnstagedChanges()
	// if err != nil {
	// 	return state, err
	// }

	state.Files, state.Insertions, state.Deletions, err = r.getInsertionsAndDeletions(false)
	if err != nil {
		return state, fmt.Errorf("r.getInsertionsAndDeletions(false) for %s : %v", r.Path, err)
	}
	state.Dirty = (state.Insertions > 0 || state.Deletions > 0)

	state.UntrackedDirs, state.UntrackedFiles, err = r.hasUntrackedFiles()
	if err != nil {
		return state, err
	}

	if a.branch {
		state.CurrentBranch, err = r.getCurrentBranch()
		if err != nil {
			return state, err
		}
	}

	state.StagedFiles, state.StagedInsertions, state.StagedDeletions, err = r.getInsertionsAndDeletions(true)
	if err != nil {
		return state, fmt.Errorf("r.getInsertionsAndDeletions(true) for %s: %v", r.Path, err)
	}
	state.StagedChanges = (state.StagedInsertions > 0 || state.StagedDeletions > 0)

	if !a.noFetch {
		err := r.fetch()
		if err != nil {
			state.RemoteState = RemoteState{-1,-1}
			return state, err
		}
	}

	remoteState, err := r.getRemoteState()
	if err != nil {
		return state, err
	}
	state.RemoteState = remoteState

	return state, nil
}

func (r *repoConfig) getCurrentBranch() (string, error){
	cmd := r.gitCommand("symbolic-ref", "--short", "HEAD")
	cmd.Stderr = nil
	out, err := cmd.Output()
	if err == nil {
		return strings.Trim(string(out), "\n"), nil
	}

	cmd = r.gitCommand("rev-parse", "--short", "HEAD")
	out, err = cmd.Output()
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("((%s))", strings.Trim(string(out), "\n")), nil
}

func generateConfig(filename string) {

	y := strings.Builder{}
	nbRepos := 0

	subdirs, err := ioutil.ReadDir(".")
	if err != nil {
		panic(err)
	}

	fmt.Fprintf(&y, "repos:\n")
	for _, f := range subdirs {
		gitdir := fmt.Sprintf("%s/.git", f.Name())
		if _, err := os.Stat(gitdir); err != nil {
			continue
		}
		nbRepos++
		repoName := f.Name()
		repoPath := fmt.Sprintf("%s/%s", os.Getenv("PWD"), f.Name())
		fmt.Fprintf(&y, "  %s:\n    path: \"%s\"\n", repoName, repoPath)
	}

	if nbRepos == 0 {
		fmt.Fprintf(os.Stderr, "No git repos found in %s\n", os.Getenv("PWD"))
	}

	if filename != "" {
		ioutil.WriteFile(filename, []byte(y.String()), 0644)
	} else {
		fmt.Printf(y.String())
	}
}

func (r repoConfig) getTimeSinceLastCommit() (time.Duration, error) {
	cmd := r.gitCommand("log", "--pretty=format:%at", "-1")
	out, err := cmd.Output()
	if err != nil {
		return 0, fmt.Errorf("Could not get time since last commit for repo '%s' : %v", r.Path, err)
	}
	var timestamp int64
	fmt.Sscanf(string(out), "%d", &timestamp)
	return time.Now().Sub(time.Unix(timestamp, 0)), nil
}

func getRepoDir(database []*repoInfo, repoName string) (string, error) {
	for _, ri := range database {
		if ri.Config.Name == repoName {

			return ri.Config.Path, nil
		}
	}
	return "", fmt.Errorf("no repo with name '%s' in database", repoName)
}


func (rs RemoteState) String() string {
	if rs.Ahead == -1 {
		return "UNKNOWN"
	}
	if rs.Ahead > 0 && rs.Behind > 0 {
		return fmt.Sprintf("Diverged +%d-%d", rs.Ahead, rs.Behind)
	} else {
		if rs.Ahead > 0 {
			return fmt.Sprintf("Ahead +%d", rs.Ahead)
		} else if rs.Behind > 0 {
			return fmt.Sprintf("Behind -%d", rs.Behind)
		} else {
			return fmt.Sprintf("Up to date")
		}
	}
}
func (rs RemoteState) ReportString() string {
	var s string
	if rs.Ahead == -1 {
		s = "UNKNOWN"
	}
	if rs.Ahead > 0 && rs.Behind > 0 {
		s = fmt.Sprintf("Diverged +%d-%d", rs.Ahead, rs.Behind)
	} else {
		if rs.Ahead > 0 {
			s = fmt.Sprintf("Ahead +%d", rs.Ahead)
		} else if rs.Behind > 0 {
			s = fmt.Sprintf("Behind -%d", rs.Behind)
		} else if rs.Ahead < 0 || rs.Behind < 0 {
			s = fmt.Sprintf("???")
		}
	}
	return s
}

func printRepoInfoHeader(printBranch bool){
	if printBranch {
		fmt.Printf("REPO                           BRANCH                REMOTE STATE     STAGED         UNSTAGED          UNTRACKED    TSLC       COMMENT\n")
	} else {
		fmt.Printf("REPO                          REMOTE STATE     STAGED         UNSTAGED          UNTRACKED    TSLC       COMMENT\n")
	}
}

func printRepoInfo(ri *repoInfo, ansiColor bool, printBranch bool) {

	var bold string
	var reset string
	var magenta string
	var yellow string
	var green string
	var red string

	// TODO: Make this function take a bool argument for colors
	// and make the decision to pass true or false based on args
	// at the call site
	if ansiColor {
		bold = "\033[;1m"
		reset = "\033[0m"
		magenta = "\033[35m"
		yellow = "\033[33m"
		green = "\033[32m"
		red = "\033[31m"
	}

	fmt.Printf("%s%-30s%s", bold, ri.Config.Name, reset)

	if printBranch {
		fmt.Printf(" %-21s ", ri.State.CurrentBranch)
	}

	if ri.State.RemoteState.Ahead != 0 || ri.State.RemoteState.Behind != 0 {
		fmt.Printf("%s%-14s%s", magenta, ri.State.RemoteState.ReportString(), reset)
	} else {
		fmt.Printf("%14s", "")
	}

	if ri.State.StagedChanges {
		fmt.Printf(" %s%s(%2df, +%-3d,-%-3d)%s", bold, yellow, ri.State.StagedFiles,  ri.State.StagedInsertions, ri.State.StagedDeletions, reset)
	} else {
		fmt.Printf("                 ")
	}

	if ri.State.Dirty {
		fmt.Printf(" %s(%2df, +%-3d,-%-3d)%s ", yellow, ri.State.Files, ri.State.Insertions, ri.State.Deletions, reset)
	} else {
		fmt.Printf("                  ")
	}

	if ri.State.UntrackedFiles != 0 || ri.State.UntrackedDirs != 0 {
		s := fmt.Sprintf("%dd,%df", ri.State.UntrackedDirs, ri.State.UntrackedFiles)
		fmt.Printf(" %s%s%-10s%s", bold, red, s, reset)
	} else {
		fmt.Printf(" %s          %s", green, reset)
	}
	fmt.Printf("   %-4d Hours", int(ri.State.TimeSinceLastCommit.Hours()))
	fmt.Printf(" %s", ri.Config.Comment)
	fmt.Printf("\n")
}

func main() {

	args := getArgs()
	if args.generateConfig {
		fmt.Printf("main: args.generateConfig");
		generateConfig("")
		return
	}

	/*
	 * Do git style subcommand thing where 'repos add' execs a file
	 * repos-add from PATH
	 */
	if len(args.posargs) > 0 {
		var subcommand string
		if args.posargs[0] == "help" {
			subcommand = fmt.Sprintf("repos-%s", args.posargs[1])
		} else {
			subcommand = fmt.Sprintf("repos-%s", args.posargs[0])
		}
		path, err := exec.LookPath(subcommand)
		if err != nil {
			fmt.Fprintf(os.Stderr, "No such subcommand '%s'\n", args.posargs[0])
			os.Exit(1)
			// syscall.Exit(1)
		}

		if args.posargs[0] == "help" {
			cmd := []string{"man", subcommand}
			err := syscall.Exec("/usr/bin/man", cmd, os.Environ())
			if err != nil {
				fmt.Fprintf(os.Stderr, "No manpage for subcommand %s\n", args.posargs[1])
				syscall.Exit(1)
			}
		}
		if args.configFile != "" {
			args.posargs = append(args.posargs, "-F", args.configFile)
		}

		err = syscall.Exec(path, args.posargs, append(os.Environ(), "FROM_REPOS=YES"))
		if err != nil {
			fmt.Fprintf(os.Stderr, "error with subcommand: %v\n", err)
			syscall.Exit(1)
		}
	}

	if args.path != "" {
		ri := repoInfo{}
		ri.Config.Name = fmt.Sprintf("-path %s", args.path)
		ri.Config.Path = args.path
		var err error
		ri.State, err = ri.Config.getState(args)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Config.getState ERROR: %v\n", err)
		}
		printRepoInfo(&ri, args.outputFormat == "ansi" || args.outputFormat == "", args.branch)
		return
	}

	home, err := os.UserHomeDir()
	if err != nil {
		panic(err)
	}

	var databaseFile string
	if args.configFile != "" {
		databaseFile = args.configFile
	} else {
		databaseFile = filepath.Join(home, ".config", "repos.yml")
	}

	database, _, err := readDatabase(databaseFile)
	// fmt.Fprintf(os.Stderr, "%#v", config)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error opening config file '%s': %+v\n", databaseFile, err)
		os.Exit(1)
	}
	if len(database) == 0 {
		fmt.Fprintf(os.Stderr, "\033[33mWARNING\033[0m No repos listed in '%s'\n", databaseFile)
	}


	if args.recent {
		showRecentCommits(database, args)
		return
	}

	if args.listNames {
		for _, ri := range database {
			fmt.Printf("%s\n", ri.Config.Name)
		}
		return
	}

	if args.listPaths {
		// Maybe I could find a more general way of listing repos with
		// that have certain predicates
		if args.behind {
			for _, ri := range database {
				if ! args.noignore && ri.Config.Ignore {
					continue
				}
				rs, err := ri.Config.getState(args)
				if err != nil {
					panic(err)
				}
				if rs.RemoteState.Behind > 0 {
					fmt.Printf("%s\n", ri.Config.Path)
				}
			}
		} else {
			for _, ri := range database {
				fmt.Printf("%s\n", ri.Config.Path)
			}
		}
		return
	}

	if args.repo != "" {
		exitCode, err := newShellInRepo(database, args.repo)
		if err != nil {
			panic(err)
		}
		os.Exit(exitCode)
	}

	if args.getDir != "" {
		repoDir, err := getRepoDir(database, args.getDir)
		if err != nil {
			panic(err)
		}
		fmt.Println(repoDir)
		return
	}


	if args.foreach != "" {
		reposForeach(args, database)
		return
	}



	sem := make(chan struct{}, args.njobs)
	infoCh := make(chan *repoInfo)
	for _, ri := range database {
		go func(r *repoInfo) {
			sem <- struct{}{}
			defer func() { <-sem }()
			var err error
			r.State, err = r.Config.getState(args)
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				r.State.RemoteState = RemoteState{-1,-1}
			}
			infoCh <- r
		}(ri)
	}

	if args.outputFormat == "json" {
		for i:= len(database) ; i > 0 ; i -= 1 {
			<- infoCh
		}
		j, err := json.Marshal(&database)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error marshalling JSON: %s\n", err)
		}
		os.Stdout.Write(j)
	} else {
		printRepoInfoHeader(args.branch)
		for i:= len(database) ; i > 0 ; i -= 1 {
			ri := <- infoCh
			if shouldPrint(args, ri) {
				printRepoInfo(ri, args.outputFormat == "ansi" || args.outputFormat == "", args.branch)
			}
		}
	}
	close(infoCh)
}

func shouldPrint(args args, ri *repoInfo) (bool){
	// fmt.Fprintf(os.Stderr, "Repo info : %+v\n", ri);
	if args.all {
		return true
	}

	if ri.State.Dirty || (ri.State.UntrackedFiles != 0) ||
		(ri.State.UntrackedDirs != 0) || ri.State.StagedChanges {
		return true
	}

	if (ri.State.RemoteState.Ahead > 0) || (ri.State.RemoteState.Behind > 0) {
		return !ri.Config.Ignore || args.noignore
	}

	return false
}


func generateShellAutocomplete(database []*repoInfo, args args, out io.Writer) error {

	for _, ri := range database {
		fmt.Fprintf(os.Stdout, "complete -f -c repos -n 'contains -- -r (commandline -opc)' -a %s -d %s\n", ri.Config.Name, ri.Config.Path)
	}

	return nil
}


func newShellInDir(directory string) (int, error) {

	fmt.Fprintf(os.Stderr, "\033[33mWARNING: This is a beta feature, maybe use rcd instead\033[0m\n")
	err := os.Chdir(directory)
	if err != nil {
		return 1, fmt.Errorf("could not cd to '%s', : %v", directory, err)
	}
	cmd := exec.Command("/bin/bash", "-l")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	fmt.Fprintf(os.Stderr, "\033[1;37m==> \033[0mStarting new shell in \033[1;32m%s\033[0m\n", directory)
	baseEnv := []string{
		"DISPLAY=" + os.Getenv("DISPLAY"),
		"HOME=" + os.Getenv("HOME"),
		"LANG=" + os.Getenv("LANG"),
		"LC_TERMINAL=" + os.Getenv("LC_TERMINAL"),
		"LC_TERMINAL_VERSION=" + os.Getenv("LC_TERMINAL_VERSION"),
		"LOGNAME=" + os.Getenv("LOGNAME"),
		"MAIL=" + os.Getenv("MAIL"),
		"SHELL=" + os.Getenv("SHELL"),
		"SSH_CLIENT=" + os.Getenv("SSH_CLIENT"),
		"SSH_CONNECTION=" + os.Getenv("SSH_CONNECTION"),
		"TERM=" + os.Getenv("TERM"),
		"TMUX=" + os.Getenv("TMUX"),
		"USER=" + os.Getenv("USER"),
	}
	cmd.Env = append(baseEnv, "REPOS_CONTEXT="+directory)
	err = cmd.Run()
	fmt.Fprintf(os.Stderr, "\033[1;37m==> \033[0mBack from new shell in \033[1;32m%s\033[0m\n", directory)
	return cmd.ProcessState.ExitCode(), nil
}

func newShellInRepo(database []*repoInfo, repoName string) (int, error) {
	for _, ri := range database {
		if ri.Config.Name == repoName {
			return newShellInDir(ri.Config.Path)
		}
	}
	return 1, fmt.Errorf("could not find repo '%s' in ~/.config/repos.yml", repoName)
}

func indentString(input string, indent string) string {
	b := strings.Builder{}
	lines := strings.Split(input, "\n")
	for _, l := range lines {
		b.WriteString(indent)
		if l != "" {
			b.WriteString(l)
		}
		b.WriteRune('\n')
	}
	return b.String()
}
// Unused function
// func getDummyRepo() *repoInfo {
//
// 	ri := repoInfo{
// 		Config: repoConfig{
// 			Path:      "/my/repo/path/focustree",
// 			Name:      "focustree",
// 			ShortName: "ft",
// 		},
// 		State: repoState{
// 			Dirty:               true,
// 			UntrackedFiles:      false,
// 			TimeSinceLastCommit: time.Unix(0, 0),
// 		},
// 	}
// 	return &ri
// }

func reposForeach(a args, database []*repoInfo){
	sem := make(chan struct{}, a.njobs)
	outputCh := make(chan struct {*repoInfo; out string; err string; code int})
	var wg sync.WaitGroup
	for _, ri := range database {
		if !a.noignore && ri.Config.Ignore {
			continue
		}
		wg.Add(1)
		go func(r *repoInfo, wg *sync.WaitGroup) {
			sem <- struct{}{}
			defer func() { <-sem }()
			cmd := r.Config.command("bash", "-c", a.foreach)
			cmd.Stderr = nil
			out, err := cmd.Output()
			var stderr string
			var exitCode int
			if err != nil {
				if exitError, ok := err.(*exec.ExitError); ok {
					exitCode = exitError.ExitCode()
					stderr = string(exitError.Stderr)
				} else {
					stderr = fmt.Sprintf("Internal error : %+v", err)
				}
			}
			outputCh <- struct{*repoInfo;out string; err string; code int}{r,strings.Trim(string(out), "\n"),strings.Trim(stderr, "\n"), exitCode}
		}(ri, &wg)
	}
	go func(wg *sync.WaitGroup) {
		for p := range outputCh {
			if a.csv {
				if p.err != "" {
					fmt.Fprintf(os.Stderr, "%s\n", p.err)
				}
				fmt.Fprintf(os.Stdout, "%s%s%s\n", p.repoInfo.Config.Name, a.csvSep, p.out)
			} else {
				fmt.Fprintf(os.Stdout, "\033[1;37m%s\033[22m: git %s ", p.repoInfo.Config.Name, a.foreach)
				if p.err == "" {
					fmt.Printf("-> \033[1;32m%d\033[0m\n", p.code)
					fmt.Fprintf(os.Stdout, "%s", indentString(p.out, "    > "))
				} else {
					fmt.Printf("-> \033[1;31m%d\033[0m\n", p.code)
					fmt.Fprintf(os.Stdout, "%s", indentString(p.err, "    X "))
				}
			}
			wg.Done()
		}
	}(&wg)
	wg.Wait()

}
