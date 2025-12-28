# Contributor License Agreement (CLA)

## repo-sapiens Project

Thank you for your interest in contributing to repo-sapiens ("the Project"), maintained by savorywatt ("Project Maintainer"). This Contributor License Agreement ("Agreement") documents the rights granted by contributors to the Project.

This is a legally binding document, so please read it carefully before agreeing to it. This Agreement is intended to be simple, fair, and protective of both contributors and the Project.

## Summary (Not Legal Advice)

In plain terms, by contributing to repo-sapiens you are agreeing that:

1. **You keep ownership of your contributions** - You retain all copyright to your work
2. **You grant us a license** - You give the Project permission to use your contributions
3. **Your contributions are under MIT** - Your code will be distributed under the same MIT license as the Project
4. **You have the right to contribute** - You confirm you're allowed to share the code you're contributing
5. **No warranties** - Like all open source contributions, these come "as is"

This is a standard, open source friendly agreement similar to those used by Apache, Django, and many other projects.

## The Agreement

### 1. Definitions

**"You"** means the individual or legal entity making this Agreement with the Project Maintainer.

**"Contribution"** means any original work of authorship, including any modifications or additions to existing work, that you submit to the Project. This includes code, documentation, configuration files, and any other copyrightable material.

**"Submit"** means any form of communication sent to the Project, including but not limited to pull requests, issue reports, code reviews, email discussions, or any electronic, written, or verbal communication.

### 2. Grant of Copyright License

Subject to the terms and conditions of this Agreement, You grant to the Project Maintainer and recipients of software distributed by the Project a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to:

- Reproduce, prepare derivative works of, publicly display, publicly perform, sublicense, and distribute Your Contributions and such derivative works under the MIT License.

This means we can use your code in the Project and distribute it under the MIT License, now and in the future.

### 3. Grant of Patent License

Subject to the terms and conditions of this Agreement, You grant to the Project Maintainer and recipients of software distributed by the Project a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable (except as stated in this section) patent license to:

- Make, have made, use, offer to sell, sell, import, and otherwise transfer your Contributions.

If anyone (including You) initiates patent litigation against the Project or any recipient claiming that a Contribution infringes a patent, any patent licenses granted under this Agreement for that Contribution terminate as of the date such litigation is filed.

### 4. You Retain Ownership

Nothing in this Agreement transfers ownership of Your Contributions to the Project Maintainer. You retain full ownership and all rights to your intellectual property. You are free to use your Contributions in other projects, relicense them, or do anything else you want with them.

### 5. Representations and Warranties

You represent and warrant that:

a) **Authority**: You are legally entitled to grant the above licenses. If your employer(s) has rights to intellectual property that you create, you represent that you have received permission to make Contributions on behalf of that employer, or that your employer has waived such rights for your Contributions to the Project.

b) **Originality**: Each of Your Contributions is Your original creation and does not violate any third party's intellectual property rights.

c) **Legal Right**: You have the legal right to grant the licenses under this Agreement.

d) **Notice of Third-Party Work**: If any part of Your Contribution is not your original creation, you will identify the source and license of that work, and submit it separately with clear attribution.

### 6. No Obligation to Use

You understand that the decision to include Your Contribution in the Project is at the sole discretion of the Project Maintainer. The Project Maintainer is under no obligation to accept, include, or maintain Your Contribution.

### 7. Disclaimer of Warranty

Your Contributions are provided "AS IS", WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE.

### 8. Limitation of Liability

In no event shall You be liable to the Project Maintainer or any recipient of Your Contributions for any damages, including any direct, indirect, special, incidental, or consequential damages arising out of the use or inability to use Your Contributions.

### 9. Agreement to Terms

You confirm that:
- You have read and understand this Agreement
- You accept and agree to be bound by this Agreement
- All information provided by You is accurate and complete

## How to Sign This Agreement

### Developer Certificate of Origin (DCO)

Instead of requiring a separate signature, this Project uses the **Developer Certificate of Origin** sign-off process. By adding a `Signed-off-by` line to your commit messages, you certify that you have read and agree to this CLA.

#### For Each Contribution

Add the following to your commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

#### Using Git Sign-Off

Git makes this easy with the `-s` flag:

```bash
git commit -s -m "feat: add new feature"
```

This automatically adds the `Signed-off-by` line using your Git configuration (`user.name` and `user.email`).

#### Configure Git (One-Time Setup)

Ensure your Git identity is configured:

```bash
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

#### For All Commits in a Pull Request

Every commit in your pull request must include the `Signed-off-by` line. If you forget, you can amend commits:

```bash
# Amend the last commit
git commit --amend -s

# Sign-off all commits in a branch (interactive rebase)
git rebase -i HEAD~N  # where N is number of commits
# In editor, change 'pick' to 'edit' for each commit
# For each commit:
git commit --amend -s
git rebase --continue
```

### What You're Certifying

By signing off, you certify that:

```
Developer Certificate of Origin
Version 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

## Questions?

If you have questions about this Agreement, please:

1. Open an issue in the project repository
2. Contact the Project Maintainer: savorywatt
3. Review similar CLAs used by other open source projects (Apache, Django, etc.)

## Version History

- **Version 1.0** (2025-12-25): Initial CLA for repo-sapiens project

---

**Project**: repo-sapiens
**License**: MIT License
**Maintainer**: savorywatt
**Last Updated**: 2025-12-25
